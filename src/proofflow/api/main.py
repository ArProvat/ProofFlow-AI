from fastapi import FastAPI

app = FastAPI(
    title="ProofFlow AI",
    version="0.1.0",
    description="Verifiable document intelligence API",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
