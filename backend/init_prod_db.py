import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from database import Base, engine as default_engine
import sys
import os

# Append the project path
sys.path.append('d:\\Web Development\\buddy-bot\\backend')

from models import *

async def run():
    url = "postgresql+asyncpg://postgres.lldcxrjxyldwiepqdaqy:a1n2u3r4a5g6@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
    print("Creating engine...")
    engine = create_async_engine(
        url,
        echo=True,
        connect_args={
            "ssl": "require"
        }
    )
    
    print("Connecting and creating tables...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("SUCCESS! Tables created.")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(run())
