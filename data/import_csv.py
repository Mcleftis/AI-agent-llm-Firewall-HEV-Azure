import pandas as pd
from db.models import SessionLocal, Telemetry
from datetime import datetime, timedelta

def import_baseline_csv():
    df = pd.read_csv('my_working_dataset.csv')
    db = SessionLocal()
    
    print("Ξεκινάει το Migration του CSV στην TimescaleDB...")
    try:
        start_time = datetime.utcnow()
        
        for index, row in df.iterrows():
            current_timestamp = start_time + timedelta(seconds=index)
            
            telemetry_record = Telemetry(
                time=current_timestamp,
                session_id="baseline_train_run",
                speed=float(row['Speed (km/h)']),
                acceleration=float(row['Acceleration (m/s²)']),
                engine_power=float(row['Engine Power (kW)']),
                battery_status="OK",
                action_taken="baseline_explore"
            )
            db.add(telemetry_record)
            
            if index % 500 == 0:
                db.commit()
                
        db.commit()
        print("Το Migration ολοκληρώθηκε! 100% Data-driven και Production Ready.")
    except Exception as e:
        db.rollback()
        print(f"Migration Failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import_baseline_csv()