import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        res = await client.post('http://localhost:8000/api/auth/operator/login', json={'employee_code': 'O-001', 'password': 'Password123!'})
        print(res.status_code, res.text)

if __name__ == '__main__':
    asyncio.run(main())
