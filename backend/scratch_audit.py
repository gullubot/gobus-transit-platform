from sqlalchemy import text
from app.db.session import SessionLocal

def main():
    db = SessionLocal()
    try:
        print("=== ROUTES COLUMNS & ROWS ===")
        res = db.execute(text("SELECT * FROM routes WHERE organization_id = '8ff4c19f-fbdb-5815-bd6d-746203b3865c'"))
        rows = list(res.mappings())
        if rows:
            print("Columns:", list(rows[0].keys()))
            for r in rows:
                print(r['id'], r.get('route_code'), r.get('route_name'))

        print("\n=== FARE SLABS FOR S-7, AC-6, S-112 ===")
        res = db.execute(text("""
            SELECT fc.name as fare_name, fs.min_distance_km, fs.max_distance_km, fs.fare_amount
            FROM fare_slabs fs
            JOIN fare_configurations fc ON fs.fare_configuration_id = fc.id
            WHERE fc.name LIKE '%S-7%' OR fc.name LIKE '%AC-6%' OR fc.name LIKE '%S-112%'
            ORDER BY fc.name, fs.min_distance_km
        """))
        for row in res.mappings():
            print(dict(row))

        print("\n=== STOPS COUNT & DISTANCE FOR S-7 (ROUTE e5b77303) ===")
        res = db.execute(text("""
            SELECT rs.stop_sequence, rs.distance_from_origin_km, s.name, s.stop_code
            FROM route_stops rs
            JOIN stops s ON rs.stop_id = s.id
            WHERE rs.route_id = 'e5b77303-160d-4598-9fce-0aef5419a170'
            ORDER BY rs.stop_sequence
        """))
        for row in res.mappings():
            print(dict(row))

    finally:
        db.close()

if __name__ == "__main__":
    main()
