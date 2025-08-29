import anyio, traceback, sys
import server

if __name__ == "__main__":
    try:
        anyio.run(server.main)
    except Exception:
        traceback.print_exc()
        sys.stderr.flush()
        raise
