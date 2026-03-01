from fastapi import FastAPI

import uvicorn
app = FastAPI()

def main():
    print("Hello from agenticblogger!")


@app.get("/health")
def health_check():
    health = {
        "status" : "running",
        "type" : "python"
    }
    return health

if __name__ == "__main__":
    uvicorn.run(app)