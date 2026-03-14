"""Quick Neon DB health check.

Prints an HTTP-style status code:
- 200 if connection and query succeed
- 500 otherwise
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv
load_dotenv()  # Load .env file for local development


def main() -> int:
	load_dotenv("backend/.env")
	db_url = os.getenv("NEONDB_DATABASE_URL", "").strip()

	if not db_url:
		print("status: 500")
		print("error: NEONDB_DATABASE_URL is missing")
		return 1

	try:
		with psycopg2.connect(db_url, sslmode="require") as conn:
			with conn.cursor() as cursor:
				cursor.execute("SELECT 1")
				cursor.fetchone()

		print("status: 200")
		print("message: Neon DB connection successful")
		return 0
	except Exception as exc:
		print("status: 500")
		print(f"error: {exc}")
		return 1


if __name__ == "__main__":
	sys.exit(main())
