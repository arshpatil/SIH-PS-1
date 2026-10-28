import os
from app import create_app

env_name = os.getenv("FLASK_ENV", "development")
app = create_app(env_name)

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "t")

    print(f"-> Starting {app.config.get('APP_NAME')}")
    print(f"-> Environment : {env_name}")
    print(f"-> Server URL  : http://{host}:{port}")
    print(f"-> Health check: http://{host}:{port}/api/health")

    app.run(host=host, port=port, debug=debug)
