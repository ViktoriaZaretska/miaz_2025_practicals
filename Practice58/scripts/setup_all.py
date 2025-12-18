import subprocess
import sys

def run(cmd):
    print(">", " ".join(cmd))
    subprocess.check_call(cmd)

def main():
    run([sys.executable, "scripts/run_sql.py", "db/schema.sql"])
    run([sys.executable, "db/seed.py"])
    print("✅ База ініціалізована. Далі: uvicorn api.main:app --reload")

if __name__ == "__main__":
    main()
