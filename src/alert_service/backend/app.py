from fastapi import FastAPI, HTTPException
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler


from src.alert_service.backend.database.db import init_db
from src.alert_service.backend.alerts.alert_handler import process_alert, validate_alert
from src.alert_service.backend.scheduler.watchlist import filter_watchlist
from termcolor import cprint
from src.alert_service.backend.alerts.alert_models import Alert, TokenInfo, PriceInfo

# Create FastAPI app instance
app = FastAPI(title="Alert Reception API", version="1.0")

@app.on_event("startup")
def startup_event():
    # Initialize the database (creates tables if they don't exist)
    init_db()
    cprint("[INFO] Database initialized.", "green")
    
    # Initialize the scheduler and add the watchlist filtering job
    scheduler = BackgroundScheduler()
    scheduler.add_job(filter_watchlist, 'interval', minutes=10)
    scheduler.start()
    app.state.scheduler = scheduler
    cprint("[INFO] Scheduler started for watchlist filtering (every 10 minutes).", "green")

@app.on_event("shutdown")
def shutdown_event():
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown()
        cprint("[INFO] Scheduler shutdown.", "yellow")

@app.post("/alert", status_code=201)
async def receive_alert(alert: Alert):
    # If no timestamp provided, set the current time
    if alert.timestamp is None:
        alert.timestamp = datetime.utcnow()
    
    # Log the received alert with colored output
    cprint(f"[INFO] Received alert for ticker: {alert.info.symbol}", "blue")
    cprint(f"Details: {alert.dict()}", "blue")

    # Validate the alert before processing
    try:
        validate_alert(alert)
    except ValueError as ve:
        cprint(f"[ERROR] Validation failed: {ve}", "red")
        raise HTTPException(status_code=400, detail=str(ve))
    
    # Process the alert (this will update the database and trigger refresh functions)
    try:
        processed_entry = process_alert(alert)
        cprint(f"[INFO] Processed alert for ticker: {alert.info.symbol}", "green")
    except Exception as e:
        cprint(f"[ERROR] Failed to process alert: {e}", "red")
        raise HTTPException(status_code=500, detail="Alert processing failed.")
    
    # Return a confirmation response
    return {"status": "success", "message": "Alert received and processed", "data": alert.dict()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)