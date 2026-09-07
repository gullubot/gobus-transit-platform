"""
Transit Platform — GoBus Simulator CLI Entry Point.

Commands:
  health:               Checks backend connectivity and status.
  inspect-assignment:   Logs in and inspects the current operator duty assignment.
  smoke-test:           Executes a single end-to-end verification loop.
  simulate:             Executes real route-driven bus movement or multi-bus scenarios.
"""

import argparse
import sys
import time
from typing import Optional

from simulator.api.assignment import fetch_operator_assignment
from simulator.api.auth import operator_login, operator_logout
from simulator.api.client import GoBusHttpClient
from simulator.api.heartbeat import send_device_heartbeat
from simulator.api.route import fetch_service_route
from simulator.api.telemetry import create_telemetry_packet, send_telemetry_batch
from simulator.api.trip import end_trip_tracking, start_trip_tracking
from simulator.config.settings import Settings, get_settings
from simulator.core.bus_simulator import BusConfig
from simulator.core.clock import SimulationClock
from simulator.core.exceptions import (
    AccountForbiddenError,
    AssignmentNotFoundError,
    AuthenticationError,
    BackendUnavailableError,
    SimulatorError,
)
from simulator.core.fleet import FleetManager
from simulator.core.movement import MovementEngine
from simulator.core.scenario import ScenarioDefinition
from simulator.core.scenario_loader import build_scenario, validate_scenario
from simulator.core.scheduler import ScenarioScheduler
from simulator.core.session import OperatorSession
from simulator.core.telemetry_generator import TelemetryGenerator
from simulator.utils.logging import get_logger, setup_logging

logger = get_logger("cli")


def cmd_health(settings: Settings) -> int:
    """Checks GoBus backend connectivity."""
    print("=" * 60)
    print(" GOBUS SIMULATOR — HEALTH CHECK")
    print("=" * 60)
    print(f"Target Backend: {settings.backend_url}")
    print(f"Timeout:        {settings.request_timeout}s\n")

    client = GoBusHttpClient(base_url=settings.backend_url, timeout=settings.request_timeout)
    try:
        health_data = client.check_health()
        print("[SUCCESS] GoBus Backend is REACHABLE and HEALTHY.")
        print(f"Response: {health_data}\n")
        return 0
    except BackendUnavailableError as e:
        print(f"[ERROR] Backend Unavailable: {e}")
        print("Please ensure the GoBus backend server is running and accessible.\n")
        return 1
    except SimulatorError as e:
        print(f"[ERROR] Health check failed: {e}\n")
        return 1
    finally:
        client.close()


def cmd_inspect_assignment(settings: Settings, employee_code: Optional[str] = None, password: Optional[str] = None) -> int:
    """Logs in and inspects duty assignment without starting tracking."""
    print("=" * 60)
    print(" GOBUS SIMULATOR — OPERATOR DUTY INSPECTION")
    print("=" * 60)
    print(f"Target Backend: {settings.backend_url}")

    primary_op = settings.get_primary_operator()
    code = employee_code or (primary_op.employee_code if primary_op else "")
    pwd = password or (primary_op.password if primary_op else "")

    if not code or not pwd:
        print("[ERROR] Missing operator credentials.")
        print("Set GOBUS_OPERATOR_EMPLOYEE_CODE and GOBUS_OPERATOR_PASSWORD in .env or via CLI flags.\n")
        return 1

    print(f"Operator Code:  {code}\n")

    client = GoBusHttpClient(base_url=settings.backend_url, timeout=settings.request_timeout)
    session = OperatorSession(employee_code=code)

    try:
        print("Step 1: Authenticating operator...")
        operator_login(client, session, pwd)
        print(f"[OK] Authenticated as {session.name} (Role: {session.role}, Org: {session.organization_name})\n")

        print("Step 2: Retrieving duty assignment...")
        assignment = fetch_operator_assignment(client, session)
        print("[OK] Duty Assignment Found:\n")
        print(f"  Assignment ID:    {assignment.assignment_id}")
        print(f"  Trip ID:          {assignment.trip_id}")
        print(f"  Service:          {assignment.service_code} — {assignment.service_name}")
        print(f"  Route:            {assignment.route_code} — {assignment.route_name}")
        print(f"  Direction:        {assignment.direction}")
        print(f"  Vehicle:          {assignment.vehicle_number} (ID: {assignment.vehicle_id})")
        print(f"  Planned Start:    {assignment.planned_start_at}")
        print(f"  Trip Status:      {assignment.trip_status}")
        print(f"  Assigned Device:  {assignment.assigned_device_id or 'None'}")
        print(f"  Active Session:   {assignment.active_tracking_session_id or 'None'}\n")
        print("Inspection complete. No tracking session was started.")
        return 0

    except AuthenticationError as e:
        print(f"[ERROR] Authentication Failed: {e}")
        return 1
    except AccountForbiddenError as e:
        print(f"[ERROR] Account Forbidden: {e}")
        return 1
    except AssignmentNotFoundError as e:
        print(f"[WARNING] {e}")
        print("Note: To simulate tracking, assign this operator to an active trip in the GoBus Admin Web.\n")
        return 2
    except BackendUnavailableError as e:
        print(f"[ERROR] Backend Unavailable: {e}")
        return 1
    except Exception as e:
        logger.exception("Unexpected error during inspection")
        print(f"[ERROR] Unexpected failure: {e}")
        return 1
    finally:
        operator_logout(session)
        client.close()


def cmd_smoke_test(settings: Settings, employee_code: Optional[str] = None, password: Optional[str] = None) -> int:
    """Executes a single end-to-end verification loop."""
    print("=" * 60)
    print(" GOBUS SIMULATOR — SINGLE-PACKET SMOKE TEST")
    print("=" * 60)
    print(f"Target Backend: {settings.backend_url}")

    primary_op = settings.get_primary_operator()
    code = employee_code or (primary_op.employee_code if primary_op else "")
    pwd = password or (primary_op.password if primary_op else "")

    if not code or not pwd:
        print("[ERROR] Missing operator credentials.")
        return 1

    client = GoBusHttpClient(base_url=settings.backend_url, timeout=settings.request_timeout)
    session = OperatorSession(employee_code=code)
    trip_started = False

    try:
        print("1. Authenticating operator...")
        operator_login(client, session, pwd)
        print(f"   [OK] Logged in: {session.name} ({session.employee_code})\n")

        print("2. Fetching duty assignment...")
        assignment = fetch_operator_assignment(client, session)
        print(f"   [OK] Assigned Trip: {assignment.trip_id[:8]}... (Vehicle: {assignment.vehicle_number})\n")

        print("3. Starting trip tracking session...")
        start_resp = start_trip_tracking(client, session)
        tracking_session_id = start_resp["tracking_session_id"]
        trip_started = True
        print(f"   [OK] Tracking Session Active: {tracking_session_id[:8]}...\n")

        print("4. Generating and sending 1 telemetry observation packet...")
        seq = session.next_sequence()
        packet = create_telemetry_packet(
            latitude=22.572646,
            longitude=88.363895,
            device_sequence=seq,
            speed_mps=5.0,
            heading=90.0,
            accuracy_m=5.0,
        )
        batch_ack = send_telemetry_batch(client, session, [packet])
        if not batch_ack.is_fully_accepted and not batch_ack.duplicates:
            print(f"   [WARN] Telemetry not accepted: rejected={batch_ack.rejected}")
        else:
            print(f"   [OK] Telemetry ACK received: accepted={len(batch_ack.accepted)}, duplicates={len(batch_ack.duplicates)}\n")

        print("5. Submitting device heartbeat...")
        hb_resp = send_device_heartbeat(client, session, battery_level=98.0)
        print(f"   [OK] Heartbeat ACK: {hb_resp.get('status')} (Device: {hb_resp.get('device_status')})\n")

        print("6. Ending trip tracking session...")
        end_trip_tracking(client, session)
        trip_started = False
        print("   [OK] Tracking Session Ended.\n")

        print("=" * 60)
        print(" SMOKE TEST PASSED SUCCESSFULLY")
        print("=" * 60)
        return 0

    except Exception as e:
        logger.exception("Smoke test failed")
        print(f"\n[ERROR] Smoke test failed: {e}\n")
        if trip_started:
            print("Attempting emergency cleanup: ending trip session...")
            try:
                end_trip_tracking(client, session)
                print("[OK] Emergency trip end sent.")
            except Exception as clean_err:
                print(f"[WARN] Could not end trip during cleanup: {clean_err}")
        return 1
    finally:
        operator_logout(session)
        client.close()


def cmd_simulate_scenario(
    settings: Settings,
    scenario_name: str,
    dry_run: bool = False,
    duration_override: Optional[float] = None,
    time_multiplier: float = 1.0,
    tick_seconds: float = 1.0,
    max_ticks: Optional[int] = None,
) -> int:
    """Executes or dry-runs a multi-bus scenario."""
    print("=" * 70)
    print(f" GOBUS SIMULATOR — SCENARIO EXECUTION: {scenario_name.upper()}")
    print("=" * 70)

    try:
        scenario = build_scenario(scenario_name, settings)
    except SimulatorError as e:
        print(f"[ERROR] {e}")
        return 1

    if duration_override:
        scenario.duration_seconds = duration_override

    # 1. Dry Run Validation
    validation_errors = validate_scenario(scenario)
    if validation_errors:
        print("\n[FAILED] Scenario validation failed:")
        for err in validation_errors:
            print(f"  - {err}")
        return 1

    print(f"Scenario Name:  {scenario.name}")
    print(f"Description:    {scenario.description}")
    print(f"Duration:       {scenario.duration_seconds or 'Unlimited'}s")
    print(f"Buses ({len(scenario.buses)}):")
    for b in scenario.buses:
        print(f"  - [{b.bus_id}] Operator: {b.employee_code} | Speed: {b.speed_mps} m/s | Multiplier: {b.time_multiplier}x")
    print(f"Scheduled Events ({len(scenario.events)}):")
    for ev in scenario.events:
        print(f"  - T+{ev.sim_time_offset_s:05.1f}s: {ev.event_type.value:20s} Target: {ev.target_bus_id:6s} {ev.parameters}")

    if dry_run:
        print("\n" + "=" * 70)
        print(" [SUCCESS] DRY-RUN VALIDATION PASSED. Zero network calls were made.")
        print("=" * 70)
        return 0

    # 2. Live Execution
    print("\nInitializing Fleet...")
    fleet = FleetManager(backend_url=settings.backend_url, request_timeout=settings.request_timeout)
    for b_conf in scenario.buses:
        fleet.add_bus(b_conf)

    scheduler = ScenarioScheduler(fleet=fleet, scenario=scenario, time_multiplier=time_multiplier)
    print("Fleet ready. Starting simulation loop. Press Ctrl+C to stop.\n" + "-" * 80)

    try:
        while not scheduler.is_completed and (max_ticks is None or scheduler.tick_count < max_ticks):
            if tick_seconds > 0:
                time.sleep(tick_seconds)

            tick_result = scheduler.tick(tick_seconds)
            sim_time = tick_result["sim_time_s"]

            # Concise multi-bus dashboard
            b_statuses = []
            for b in fleet.buses.values():
                m_state = b.movement.get_state() if b.movement else None
                if b.lifecycle.value == "RUNNING" and m_state:
                    mode_str = f"DWELL({m_state.dwell_time_remaining_s:.0f}s)" if m_state.is_dwelling else f"{m_state.current_speed_mps:.1f}m/s"
                    curr = m_state.current_stop.stop_name[:8]
                    nxt = m_state.next_stop.stop_name[:8] if m_state.next_stop else "END"
                    b_statuses.append(f"{b.bus_id}: {b.lifecycle.value}({curr}->{nxt} {mode_str})")
                else:
                    b_statuses.append(f"{b.bus_id}: {b.lifecycle.value}")

            ev_str = f" | EV: {','.join(tick_result['events_processed'])}" if tick_result["events_processed"] else ""
            print(f"[T+{sim_time:05.1f}s] {' | '.join(b_statuses)}{ev_str}")

        print("-" * 80)
        print(f"\n[COMPLETE] Scenario '{scenario.name}' completed successfully.")
        return 0

    except KeyboardInterrupt:
        print("\n[INTERRUPT] Stopping scenario cleanly...")
        fleet.emergency_cleanup()
        return 0
    except Exception as e:
        logger.exception("Scenario execution error")
        print(f"\n[ERROR] Scenario failed: {e}")
        fleet.emergency_cleanup()
        return 1
    finally:
        fleet.stop_fleet()


def cmd_simulate_single(
    settings: Settings,
    employee_code: Optional[str] = None,
    password: Optional[str] = None,
    speed_mps: float = 8.33,
    tick_seconds: float = 1.0,
    time_multiplier: float = 1.0,
    dwell_seconds: float = 15.0,
    max_ticks: Optional[int] = None,
    auto_end: bool = True,
) -> int:
    """Executes simple single-bus movement simulation."""
    print("=" * 60)
    print(" GOBUS SIMULATOR — SINGLE BUS ROUTE MOVEMENT")
    print("=" * 60)
    print(f"Target Backend:   {settings.backend_url}")
    print(f"Cruise Speed:     {speed_mps:.1f} m/s ({speed_mps * 3.6:.1f} km/h)")
    print(f"Tick Interval:    {tick_seconds:.1f}s (Multiplier: {time_multiplier}x)")
    print(f"Stop Dwell Time:  {dwell_seconds:.1f}s")
    if max_ticks:
        print(f"Max Ticks Limit:  {max_ticks}")
    print("=" * 60)

    primary_op = settings.get_primary_operator()
    code = employee_code or (primary_op.employee_code if primary_op else "")
    pwd = password or (primary_op.password if primary_op else "")

    if not code or not pwd:
        print("[ERROR] Missing operator credentials.")
        return 1

    client = GoBusHttpClient(base_url=settings.backend_url, timeout=settings.request_timeout)
    session = OperatorSession(employee_code=code)
    trip_started = False

    try:
        print("\nStep 1: Authenticating operator...")
        operator_login(client, session, pwd)
        print(f"[OK] Authenticated: {session.name} ({session.employee_code}) [Org: {session.organization_name}]")

        print("\nStep 2: Retrieving duty assignment...")
        assignment = fetch_operator_assignment(client, session)
        print(f"[OK] Assigned Trip: {assignment.trip_id}")
        print(f"     Service: {assignment.service_code} ({assignment.service_name})")
        print(f"     Vehicle: {assignment.vehicle_number} | Direction: {assignment.direction}")

        print("\nStep 3: Loading real route topology from backend...")
        route = fetch_service_route(
            client=client,
            service_id=assignment.service_id,
            organization_id=session.organization_id or "",
            direction=assignment.direction,
        )
        print(f"[OK] Route Loaded: {route.route_code} ({route.route_name})")
        print(f"     Stops: {route.stop_count} | Segments: {route.segment_count} | Total Distance: {route.total_distance_m / 1000.0:.2f} km")

        print("\nStep 4: Starting active tracking session...")
        start_resp = start_trip_tracking(client, session)
        trip_started = True
        print(f"[OK] Tracking Session Started: {start_resp['tracking_session_id']}")

        clock = SimulationClock(time_multiplier=time_multiplier)
        movement = MovementEngine(
            route=route,
            cruise_speed_mps=speed_mps,
            dwell_duration_seconds=dwell_seconds,
        )
        telemetry_gen = TelemetryGenerator(session=session, clock=clock)

        print("\nStep 5: Starting movement simulation loop...")
        print("Press Ctrl+C to cleanly stop simulation and end trip.\n" + "-" * 80)

        tick_count = 0
        last_heartbeat_time = 0.0

        while not movement.is_completed and (max_ticks is None or tick_count < max_ticks):
            if tick_seconds > 0:
                time.sleep(tick_seconds)

            tick_count += 1
            sim_time = clock.tick(tick_seconds)
            state = movement.advance(tick_seconds * time_multiplier)
            packet = telemetry_gen.generate_packet(state)

            ack = send_telemetry_batch(client, session, [packet])

            if clock.elapsed_sim_seconds - last_heartbeat_time >= 30.0:
                try:
                    send_device_heartbeat(client, session, battery_level=packet.get("battery_level"))
                    last_heartbeat_time = clock.elapsed_sim_seconds
                except Exception as hb_err:
                    logger.debug(f"Heartbeat tick error: {hb_err}")

            dwell_str = f"DWELLING ({state.dwell_time_remaining_s:.0f}s)" if state.is_dwelling else "CRUISING"
            status_summary = (
                f"Tick {tick_count:04d} | Sim {sim_time.strftime('%H:%M:%S')} | "
                f"Progress {state.total_progress_m / 1000.0:.2f}km/{route.total_distance_m / 1000.0:.2f}km | "
                f"{state.current_stop.stop_name[:14]:14s} -> {state.next_stop.stop_name[:14] if state.next_stop else 'END':14s} | "
                f"{dwell_str:13s} | Spd {state.current_speed_mps:4.1f}m/s | Hdg {state.current_heading:5.1f}° | "
                f"ACK={'OK' if ack.is_fully_accepted else 'ERR'}"
            )
            print(status_summary)

        print("-" * 80)
        if movement.is_completed:
            print(f"\n[COMPLETE] Bus reached final destination stop '{route.stops[-1].stop_name}'.")

        if auto_end:
            print("\nStep 6: Ending trip tracking session...")
            end_trip_tracking(client, session)
            trip_started = False
            print("[OK] Tracking session closed cleanly.")

        return 0

    except KeyboardInterrupt:
        print("\n[INTERRUPT] Received user stop signal. Ending simulation cleanly...")
        if trip_started:
            try:
                end_trip_tracking(client, session)
                print("[OK] Trip session cleanly ended.")
            except Exception as e:
                print(f"[WARN] Error ending trip session: {e}")
        return 0
    except Exception as e:
        logger.exception("Simulation error")
        print(f"\n[ERROR] Simulation failed: {e}")
        if trip_started:
            try:
                end_trip_tracking(client, session)
                print("[OK] Emergency trip end sent.")
            except Exception as clean_err:
                print(f"[WARN] Cleanup failed: {clean_err}")
        return 1
    finally:
        operator_logout(session)
        client.close()


def cmd_day_plan(
    settings: Settings,
    manifest_path: Optional[str] = None,
    service_date: Optional[str] = None,
    dry_run: bool = False,
    export_plan_path: Optional[str] = None,
    step_seconds: float = 60.0,
) -> int:
    """Processes, validates, exports, or dry-runs a full service day plan."""
    from simulator.service_day.manifest import load_manifest, create_default_manifest
    from simulator.service_day.planner import ServiceDayPlanner, PlanValidationError
    from simulator.service_day.scheduler import ServiceDayScheduler

    print("=" * 70)
    print(" GOBUS SIMULATOR — SERVICE-DAY PLANNER (PHASE 5B)")
    print("=" * 70)

    try:
        if manifest_path:
            print(f"Loading manifest: {manifest_path}")
            manifest = load_manifest(manifest_path)
        else:
            date_str = service_date or datetime.now().strftime("%Y-%m-%d")
            print(f"Generating default Kolkata service manifest for date: {date_str}")
            manifest = create_default_manifest(service_date=date_str)
    except Exception as e:
        print(f"\n[ERROR] Failed to load manifest: {e}")
        return 1

    try:
        plan = ServiceDayPlanner.build_plan(manifest)
    except PlanValidationError as e:
        print("\n[VALIDATION FAILED]")
        for err in e.errors:
            print(f"  - {err}")
        return 1

    print("\n[PLAN SPECIFICATION]")
    print(f"  Service Date:              {plan.service_date}")
    print(f"  Timezone:                  {plan.timezone_name}")
    print(f"  First Departure:           {plan.first_departure.strftime('%H:%M:%S') if plan.first_departure else 'None'}")
    print(f"  Final Arrival:             {plan.final_arrival.strftime('%H:%M:%S') if plan.final_arrival else 'None'}")
    print(f"  Total Operating Span:      {round(plan.total_duration_s / 3600.0, 2)} hours ({round(plan.total_duration_s)}s)")

    if plan.fleet_coverage:
        print(f"\n[FLEET UTILIZATION ({plan.fleet_coverage.total_vehicles} vehicles)]")
        print(f"  Active Vehicles:           {plan.fleet_coverage.active_vehicles_with_duties}")
        print(f"  Idle Vehicles:             {plan.fleet_coverage.idle_vehicles_without_duties}")
        print(f"  Max Simultaneous Buses:    {plan.fleet_coverage.max_simultaneous_vehicles}")
        print(f"  Total Scheduled Trips:     {plan.fleet_coverage.total_scheduled_trips}")

    print("\n[VEHICLE DUTIES]")
    for vid, duty in plan.vehicle_duties.items():
        print(f"  - [{duty.vehicle_number}] ({duty.vehicle_type}): {duty.trip_count} sequential trip(s)")
        for t in duty.trips:
            p_end_str = t.planned_end.strftime('%H:%M') if t.planned_end else '??:??'
            print(f"      • {t.planned_start.strftime('%H:%M')} - {p_end_str} | {t.service_code} ({t.direction}) | Operator: {t.operator_code} | Trip: {t.trip_id[:8]}...")

    print("\n[SERVICES COVERED]")
    for sc in plan.service_coverages:
        headway_str = f"{sc.headway_minutes} mins" if sc.headway_minutes else "N/A"
        print(f"  - [{sc.service_code}] Direction: {sc.direction} | Trips: {sc.trip_count} | Operating: {sc.first_departure.strftime('%H:%M')} to {sc.final_departure.strftime('%H:%M')} | Headway: {headway_str}")

    print("\n[VALIDATION]")
    print("  PASS: Plan structure, turnaround times, and single-operator assignments verified.")

    if export_plan_path:
        import json
        from pathlib import Path
        p = Path(export_plan_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(plan.to_dict(), f, indent=2)
        print(f"\n[EXPORT] Plan exported safely (zero secrets) to: {p.resolve()}")

    if dry_run:
        print("\n" + "=" * 70)
        print(" FULL-FLEET DRY-RUN SIMULATION (OFFLINE)")
        print("=" * 70)
        scheduler = ServiceDayScheduler(plan=plan, settings=settings, dry_run=True)
        results = scheduler.run_dry_run_full_day(step_seconds=step_seconds)
        print(f"Status:                      {results['status']}")
        print(f"Total Trips Executed:        {results['completed_trips']} / {results['total_trips']}")
        print(f"Failed Trips:                {results['failed_trips']}")
        print(f"Simulated Operating Span:    {results['simulated_duration_hours']} hours ({results['simulated_duration_s']}s)")
        print(f"Wall-Clock Execution Time:   {results['wall_clock_time_s']} seconds")
        print(f"Scheduler Ticks:             {results['ticks_executed']}")
        print("=" * 70)

    return 0


def cmd_service_day(
    settings: Settings,
    manifest_path: Optional[str] = None,
    service_date: Optional[str] = None,
    time_multiplier: float = 1.0,
    tick_seconds: float = 1.0,
    dry_run: bool = False,
    max_trips: Optional[int] = None,
    max_simulated_minutes: Optional[float] = None,
    max_duration_seconds: Optional[float] = None,
    no_auto_end: bool = False,
) -> int:
    """Executes a full-fleet service-day simulation either live against GoBus or locally via dry-run."""
    from simulator.service_day.manifest import load_manifest, create_default_manifest
    from simulator.service_day.planner import ServiceDayPlanner, PlanValidationError
    from simulator.service_day.executor import ServiceDayExecutor

    print("=" * 70)
    print(" GOBUS SIMULATOR — FULL-FLEET SERVICE-DAY ENGINE (PHASE 5C)")
    print("=" * 70)

    # 1. Load manifest
    try:
        if manifest_path:
            print(f"Loading manifest: {manifest_path}")
            manifest = load_manifest(manifest_path)
        else:
            date_str = service_date or datetime.now().strftime("%Y-%m-%d")
            print(f"Generating default Kolkata service manifest for date: {date_str}")
            manifest = create_default_manifest(service_date=date_str)
    except Exception as e:
        print(f"\n[ERROR] Failed to load manifest: {e}")
        return 1

    # 2. Build and validate plan
    try:
        plan = ServiceDayPlanner.build_plan(manifest)
    except PlanValidationError as e:
        print("\n[VALIDATION FAILED]")
        for err in e.errors:
            print(f"  - {err}")
        return 1

    # 3. Live safety pre-check
    if not dry_run:
        print(f"Connecting to GoBus backend at: {settings.backend_url}...")
        client = GoBusHttpClient(base_url=settings.backend_url, timeout=settings.request_timeout)
        try:
            health = client.check_health()
            print(f"[OK] Backend Healthy: {health.get('status')} ({health.get('service')})\n")
        except Exception as e:
            print(f"[ERROR] GoBus Backend Unavailable: {e}")
            print("Cannot run live service-day execution without operational backend.")
            return 1
        finally:
            client.close()

    print(f"Service Date:              {plan.service_date}")
    print(f"Timezone:                  {plan.timezone_name}")
    print(f"Total Scheduled Trips:     {len(plan.trips)}")
    print(f"Planned Vehicles:          {len(plan.vehicle_duties)}")
    print(f"Time Multiplier:           {time_multiplier}x")
    print(f"Tick Interval:             {tick_seconds}s")
    print(f"Execution Mode:            {'DRY-RUN (OFFLINE)' if dry_run else 'LIVE OPERATIONAL (REAL BACKEND)'}")
    print("=" * 70)

    executor = ServiceDayExecutor(plan=plan, settings=settings, dry_run=dry_run)
    executor.clock.set_multiplier(time_multiplier)

    try:
        status = executor.run_live(
            max_duration_seconds=max_duration_seconds,
            max_trips=max_trips,
            tick_seconds=tick_seconds,
            max_simulated_minutes=max_simulated_minutes,
        )

        print("\n" + "=" * 70)
        print(" SERVICE-DAY EXECUTION SUMMARY")
        print("=" * 70)
        print(f"Final State:               {status['state']}")
        print(f"Real Wall-Clock Time:      {status['real_elapsed_seconds']} seconds")
        print(f"Simulated Operational Time:{status['elapsed_service_hours']} hours ({status['elapsed_service_seconds']}s)")
        print(f"Fleet Status:              Planned={status['fleet']['planned']}, Active={status['fleet']['active']}, Running={status['fleet']['running']}, Completed={status['fleet']['completed']}, Error={status['fleet']['error']}")
        print(f"Trips Status:              Total={status['trips']['total']}, Pending={status['trips']['pending']}, Running={status['trips']['running']}, Completed={status['trips']['completed']}, Error={status['trips']['error']}")
        print(f"Telemetry Emitted:         Packets Sent={status['telemetry']['packets_sent']}, Accepted={status['telemetry']['packets_accepted']}, Heartbeats={status['telemetry']['heartbeats_sent']}")
        print("=" * 70)
        return 0 if status['trips']['error'] == 0 else 1

    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Stopping service-day simulation...")
        executor.stop()
        return 130
    except Exception as e:
        logger.exception("ServiceDayExecutor exception")
        print(f"\n[ERROR] Service-day execution failed: {e}")
        executor.stop()
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="GoBus Standalone Demo Simulator")
    parser.add_argument(
        "command",
        choices=["health", "inspect-assignment", "smoke-test", "simulate", "ui", "day-plan", "service-day"],
        help="Command to execute",
    )
    parser.add_argument("--backend-url", type=str, help="Override backend URL")
    parser.add_argument("--employee-code", type=str, help="Override operator employee code")
    parser.add_argument("--password", type=str, help="Override operator password")
    parser.add_argument("--timeout", type=float, help="Override HTTP timeout in seconds")
    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")

    # UI server options
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface to bind Mission Control server (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind Mission Control server (default: 8080)")

    # Simulate options
    parser.add_argument("--scenario", type=str, help="Scenario to run (e.g. normal_single_bus, multi_bus_demo, delay_demo, offline_demo, crowding_demo, service_shortage_demo, full_demo)")
    parser.add_argument("--dry-run", action="store_true", help="Perform offline validation of scenario without network calls")
    parser.add_argument("--duration", type=float, help="Override scenario duration in seconds")
    parser.add_argument("--speed", type=float, default=8.33, help="Simulated bus cruise speed in m/s (default: 8.33 m/s = 30 km/h)")
    parser.add_argument("--tick", type=float, default=1.0, help="Real-world tick interval in seconds (default: 1.0s)")
    parser.add_argument("--multiplier", type=float, default=1.0, help="Simulation time speed multiplier (default: 1.0x)")
    parser.add_argument("--dwell", type=float, default=15.0, help="Dwell time at intermediate stops in seconds (default: 15.0s)")
    parser.add_argument("--max-ticks", type=int, help="Maximum number of ticks to simulate before exiting")
    parser.add_argument("--no-auto-end", action="store_true", help="Do not automatically end the trip upon route completion")

    # Service-Day / Day-Plan options (Phase 5B & 5C)
    parser.add_argument("--manifest", type=str, help="Path to service_day_manifest.json")
    parser.add_argument("--date", type=str, help="Operating service date (YYYY-MM-DD)")
    parser.add_argument("--export-plan", type=str, help="Export resolved service_day_plan.json path")
    parser.add_argument("--step-seconds", type=float, default=60.0, help="Step progression seconds for full-day dry-run (default: 60.0s)")
    parser.add_argument("--max-trips", type=int, help="Stop after N trips complete")
    parser.add_argument("--max-simulated-minutes", type=float, help="Stop after N simulated minutes pass")
    parser.add_argument("--max-duration-seconds", type=float, help="Stop after N wall-clock seconds elapse")

    args = parser.parse_args()

    settings = get_settings()
    if args.backend_url:
        settings.backend_url = args.backend_url.rstrip("/")
    if args.timeout:
        settings.request_timeout = args.timeout
    if args.log_level:
        settings.log_level = args.log_level.upper()

    setup_logging(level=settings.log_level)

    if args.command == "health":
        sys.exit(cmd_health(settings))
    elif args.command == "inspect-assignment":
        sys.exit(cmd_inspect_assignment(settings, employee_code=args.employee_code, password=args.password))
    elif args.command == "smoke-test":
        sys.exit(cmd_smoke_test(settings, employee_code=args.employee_code, password=args.password))
    elif args.command == "ui":
        from simulator.server.app import run_server
        run_server(host=args.host, port=args.port)
        sys.exit(0)
    elif args.command == "day-plan":
        sys.exit(
            cmd_day_plan(
                settings=settings,
                manifest_path=args.manifest,
                service_date=args.date,
                dry_run=args.dry_run,
                export_plan_path=args.export_plan,
                step_seconds=args.step_seconds,
            )
        )
    elif args.command == "service-day":
        sys.exit(
            cmd_service_day(
                settings=settings,
                manifest_path=args.manifest,
                service_date=args.date,
                time_multiplier=args.multiplier,
                tick_seconds=args.tick,
                dry_run=args.dry_run,
                max_trips=args.max_trips,
                max_simulated_minutes=args.max_simulated_minutes,
                max_duration_seconds=args.max_duration_seconds,
                no_auto_end=args.no_auto_end,
            )
        )
    elif args.command == "simulate":
        if args.scenario or args.dry_run:
            scenario_name = args.scenario or "normal_single_bus"
            sys.exit(
                cmd_simulate_scenario(
                    settings=settings,
                    scenario_name=scenario_name,
                    dry_run=args.dry_run,
                    duration_override=args.duration,
                    time_multiplier=args.multiplier,
                    tick_seconds=args.tick,
                    max_ticks=args.max_ticks,
                )
            )
        else:
            sys.exit(
                cmd_simulate_single(
                    settings=settings,
                    employee_code=args.employee_code,
                    password=args.password,
                    speed_mps=args.speed,
                    tick_seconds=args.tick,
                    time_multiplier=args.multiplier,
                    dwell_seconds=args.dwell,
                    max_ticks=args.max_ticks,
                    auto_end=not args.no_auto_end,
                )
            )


if __name__ == "__main__":
    main()



