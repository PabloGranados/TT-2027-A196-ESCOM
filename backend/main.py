from fastapi import FastAPI

app = FastAPI(
    title="API TT ESCOM",
    description="Backend para recomendación de laptops y tabletas"
)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "¡Entorno Backend de la ESCOM configurado y corriendo exitosamente!"}