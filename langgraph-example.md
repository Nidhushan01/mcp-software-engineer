# Supervisor report: Login returns 401 after refresh.

Classification: `bug_investigation`

## Investigation plan

1. Locate authentication endpoints
2. Locate access-token creation
3. Locate refresh-token creation
4. Locate JWT verification
5. Inspect authentication configuration
6. Inspect relevant tests
7. Inspect recent changes
8. Form competing hypotheses
9. Validate hypotheses against evidence
10. Produce evidence-backed recommendations

## Evidence

- **E1** — `app/api/auth.py:10` — Search for 'Login' matched: def login(username: str, password: str) -> dict[str, str]:
- **E2** — `app/tests/test_auth.py:4` — Search for 'returns' matched: def test_create_access_token_returns_text() -> None:
- **E3** — `app/api/auth.py:13` — Search for '401' matched: raise HTTPException(status_code=401, detail="Invalid credentials")
- **E4** — `repository` — Repository-wide search found no matches for 'refresh'.
- **E5** — `app/api/auth.py` — Authentication-related filename discovered: app/api/auth.py
- **E6** — `app/services/auth_service.py` — Authentication-related filename discovered: app/services/auth_service.py
- **E7** — `app/tests/test_auth.py` — Authentication-related filename discovered: app/tests/test_auth.py
- **E8** — `app/services/auth_service.py:16` — Token creation symbol found: create_access_token (function)
- **E9** — `app/api/auth.py:1` — Framework import traces an API module: from fastapi import APIRouter, HTTPException
- **E10** — `app/api/users.py:1` — Framework import traces an API module: from fastapi import APIRouter
- **E11** — `app/main.py:1` — Framework import traces an API module: from fastapi import FastAPI
- **E12** — `app/api/auth.py:6` — Search for 'authentication' matched: router = APIRouter(prefix="/auth", tags=["authentication"])
- **E13** — `app/core/config.py:4` — Search for 'JWT' matched: JWT_SECRET = os.getenv("JWT_SECRET", "development-secret-change-me")
- **E14** — `app/core/config.py:5` — Search for 'JWT' matched: JWT_ALGORITHM = "HS256"
- **E15** — `app/services/auth_service.py:3` — Search for 'JWT' matched: import jwt
- **E16** — `app/services/auth_service.py:6` — Search for 'JWT' matched: from app.core.config import ACCESS_TOKEN_MINUTES, JWT_ALGORITHM, JWT_SECRET
- **E17** — `app/services/auth_service.py:18` — Search for 'JWT' matched: return jwt.encode({"sub": username, "exp": expires_at}, JWT_SECRET, algorithm=JWT_ALGORITHM)
- **E18** — `requirements.txt:2` — Search for 'JWT' matched: PyJWT==2.10.1
- **E19** — `repository` — Repository-wide search found no matches for 'jwt.decode'.

## Ranked hypotheses

### H2: Tokens are signed, but no JWT verification path is implemented.
- Status: **supported**
- Confidence: **0.89**
- Evidence: E13, E16, E19
- Recommendation: Add JWT decode validation for signature, expiry, token type, issuer, and audience.

### H3: The observed 401 originates in the login credential check, not a refresh handler.
- Status: **supported**
- Confidence: **0.84**
- Evidence: E3
- Recommendation: Add separate tests for login failure, access-token expiry, and refresh failure.

### H1: Refresh-token creation or handling is absent.
- Status: **supported**
- Confidence: **0.71**
- Evidence: E4
- Recommendation: Implement and test refresh-token issuance/validation, or stop clients from calling refresh.

## Supervisor review

- Classified request as bug_investigation and created a 10-step plan.
- More evidence required: authentication, JWT, jwt.decode
- No additional evidence requested; route to synthesis.
