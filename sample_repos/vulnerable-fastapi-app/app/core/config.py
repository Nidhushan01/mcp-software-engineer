import os


JWT_SECRET = os.getenv("JWT_SECRET", "development-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 30
