import argparse
import asyncio
import uuid
import datetime
from rich.console import Console
from rich.live import Live
from rich.table import Table

from src.config import load_config, AppConfig, OperatorConfig
from src.client import SimulatorClient
from src.physics import RoutePhysics, SimulationClock
from src.scenarios import ScenarioEngine, ScenarioType

console = Console()

async def simulate_vehicle(config: AppConfig, op_config: OperatorConfig, status_dict: dict):
    client = SimulatorClient(base_url=config.api.base_url)
    vehicle_id = "UNKNOWN"
    status_dict[op_config.username] = {"status": "INITIALIZING", "vehicle": vehicle_id, "scenario": op_config.scenario}
    
    try:
        # 1. Login
        success = await client.login(op_config.username, op_config.password)
        if not success:
            status_dict[op_config.username]["status"] = "AUTH_FAILED"
            return
            
        # 2. Get Assignment
        status_dict[op_config.username]["status"] = "FETCHING_ASSIGNMENT"
        assignment = await client.get_my_assignment()
        if not assignment or not assignment.get("trip_id"):
            status_dict[op_config.username]["status"] = "NO_ASSIGNMENT"
            return
            
        trip_id = assignment["trip_id"]
        vehicle_id = assignment.get("vehicle_id", "UNKNOWN")
        status_dict[op_config.username]["vehicle"] = vehicle_id
        service_id = assignment.get("service_id")
        
        # 3. Discover Route
        status_dict[op_config.username]["status"] = "DISCOVERING_ROUTE"
        sd5_route = await client.get_service_route(service_id)
        stops = sd5_route.get("stops", [])
        
        # Reverse stops if direction is B_TO_A
        if op_config.direction == "B_TO_A":
            stops = stops[::-1]
            
        # 4. Start Trip
        status_dict[op_config.username]["status"] = "STARTING_TRIP"
        start_resp = await client.start_trip(trip_id)
        session_id = start_resp.get("tracking_session_id")
        
        if not session_id:
            status_dict[op_config.username]["status"] = "SESSION_FAILED"
            return
            
        # 5. Initialize Physics and Scenarios
        physics = RoutePhysics(stops)
        # Assume a 1-hour route for duration calculation
        clock = SimulationClock(multiplier=config.simulation.speed_multiplier, duration_seconds=3600)
        scenario = ScenarioEngine(op_config.scenario)
        
        base_speed_mps = 5.0 # Normal bus speed ~18 km/h
        interval = config.simulation.telemetry_interval_real_seconds
        
        seq = 1
        has_sent_crowding = False
        
        status_dict[op_config.username]["status"] = "EN_ROUTE"
        
        # 6. Main Loop
        while not physics.is_complete():
            await asyncio.sleep(interval)
            
            scenario.update(interval)
            sim_time = clock.tick(interval)
            
            speed = scenario.get_speed_mps(base_speed_mps)
            distance_km = (speed * (interval * clock.multiplier)) / 1000.0
            
            lat, lon, bearing = physics.move(distance_km)
            
            status_dict[op_config.username]["lat"] = f"{lat:.4f}"
            status_dict[op_config.username]["lon"] = f"{lon:.4f}"
            status_dict[op_config.username]["sim_time"] = sim_time.strftime("%H:%M:%S")
            status_dict[op_config.username]["scenario"] = scenario.scenario.value
            
            if scenario.should_send_telemetry(interval):
                packet = {
                    "packet_id": str(uuid.uuid4()),
                    "device_sequence": seq,
                    "latitude": lat,
                    "longitude": lon,
                    "accuracy_m": 5.0,
                    "speed_mps": speed,
                    "heading": bearing,
                    "observed_at": sim_time.isoformat(),
                    "battery_level": 90.0,
                    "network_type": "4G",
                    "gps_status": "GRANTED"
                }
                
                success = await client.send_telemetry_batch(session_id, [packet])
                seq += 1
                status_dict[op_config.username]["last_api"] = "200 OK" if success else "FAILED"
            else:
                status_dict[op_config.username]["last_api"] = "STALE (NO_SEND)"
                
            if scenario.scenario == ScenarioType.CROWDING and not has_sent_crowding:
                # Send a crowding report mid-route
                if physics.current_distance_km > physics.total_distance_km * 0.5:
                    await client.send_crowding_report(vehicle_id, "HIGH", sim_time.isoformat())
                    has_sent_crowding = True
                    status_dict[op_config.username]["last_api"] = "200 CROWDING"
        
        # 7. End Trip
        status_dict[op_config.username]["status"] = "ENDING_TRIP"
        await client.end_trip(trip_id)
        status_dict[op_config.username]["status"] = "COMPLETED"
        
    except Exception as e:
        status_dict[op_config.username]["status"] = f"ERROR: {str(e)}"
    finally:
        await client.close()


def generate_table(status_dict: dict) -> Table:
    table = Table(title="Demo Simulator Dashboard")
    table.add_column("Operator", style="cyan")
    table.add_column("Vehicle", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Scenario", style="yellow")
    table.add_column("Sim Time", justify="right")
    table.add_column("Lat/Lon", justify="right")
    table.add_column("API Status", justify="right")
    
    for op, data in status_dict.items():
        table.add_row(
            op,
            data.get("vehicle", "-"),
            data.get("status", "-"),
            data.get("scenario", "-"),
            data.get("sim_time", "-"),
            f"{data.get('lat', '-')} / {data.get('lon', '-')}",
            data.get("last_api", "-")
        )
    return table

async def main():
    parser = argparse.ArgumentParser(description="GoBus Demo Simulator")
    parser.add_argument("--config", type=str, default="config.json", help="Path to config file")
    args = parser.parse_args()
    
    try:
        config = load_config(args.config)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        return

    status_dict = {}
    
    tasks = []
    for op_config in config.operators:
        tasks.append(simulate_vehicle(config, op_config, status_dict))
        
    with Live(generate_table(status_dict), refresh_per_second=2, console=console) as live:
        # Start a background task to update UI
        async def update_ui():
            while True:
                live.update(generate_table(status_dict))
                await asyncio.sleep(0.5)
                
        ui_task = asyncio.create_task(update_ui())
        
        await asyncio.gather(*tasks)
        ui_task.cancel()
        
    console.print("[bold green]Simulation Complete.[/bold green]")
    console.print(status_dict)

if __name__ == "__main__":
    asyncio.run(main())
