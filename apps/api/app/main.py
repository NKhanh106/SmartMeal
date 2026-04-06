from fastapi import FastAPI

app = FastAPI(title="SmartMeal API")

@app.get("/")
def root():
    return {"message": "Welcome to SmartMeal API"}
