# Investigation report: Login returns 401 after refresh.

## Investigation plan

1. [complete] Locate authentication endpoints
2. [complete] Locate access-token creation
3. [complete] Locate refresh-token creation
4. [complete] Locate JWT verification
5. [complete] Inspect authentication configuration
6. [complete] Inspect relevant tests
7. [skipped] Inspect recent changes
8. [complete] Form competing hypotheses
9. [complete] Validate hypotheses against evidence
10. [complete] Produce evidence-backed recommendations

## Evidence

### E1

- Source: repository
- Location: app/api/auth.py:6
- Observation: Search for 'authentication' matched: router = APIRouter(prefix="/auth", tags=["authentication"])
- Quality: 0.76

### E2

- Source: repository
- Location: app/core/config.py:4
- Observation: Search for 'JWT' matched: JWT_SECRET = os.getenv("JWT_SECRET", "development-secret-change-me")
- Quality: 0.76

### E3

- Source: repository
- Location: app/core/config.py:5
- Observation: Search for 'JWT' matched: JWT_ALGORITHM = "HS256"
- Quality: 0.76

### E4

- Source: repository
- Location: app/services/auth_service.py:3
- Observation: Search for 'JWT' matched: import jwt
- Quality: 0.76

### E5

- Source: repository
- Location: app/services/auth_service.py:6
- Observation: Search for 'JWT' matched: from app.core.config import ACCESS_TOKEN_MINUTES, JWT_ALGORITHM, JWT_SECRET
- Quality: 0.76

### E6

- Source: repository
- Location: app/services/auth_service.py:18
- Observation: Search for 'JWT' matched: return jwt.encode({"sub": username, "exp": expires_at}, JWT_SECRET, algorithm=JWT_ALGORITHM)
- Quality: 0.76

### E7

- Source: repository
- Location: requirements.txt:2
- Observation: Search for 'JWT' matched: PyJWT==2.10.1
- Quality: 0.76

### E8

- Source: repository
- Location: app/api/auth.py:13
- Observation: Search for '401' matched: raise HTTPException(status_code=401, detail="Invalid credentials")
- Quality: 0.85

### E9

- Source: repository
- Location: repository
- Observation: A repository-wide search found no refresh-token implementation or refresh endpoint.
- Quality: 0.85

### E10

- Source: repository
- Location: repository
- Observation: A repository-wide search found JWT signing references but no jwt.decode verification call.
- Quality: 0.77

## Hypotheses

### H2: JWT tokens are signed, but no JWT verification path is implemented.

- Status: **supported**
- Confidence: **0.89**
- Supporting evidence: E2, E10
- Contradicting evidence: none
- Recommendation: Add JWT decoding and validation for signature, expiry, token type, issuer, and audience.

### H3: The 401 is produced by the login credential check rather than token refresh.

- Status: **supported**
- Confidence: **0.89**
- Supporting evidence: E1, E8
- Contradicting evidence: none
- Recommendation: Add tests that distinguish failed login, expired access token, and failed refresh responses.

### H1: The 401 occurs because refresh-token creation or handling is not implemented.

- Status: **supported**
- Confidence: **0.84**
- Supporting evidence: E9
- Contradicting evidence: none
- Recommendation: Implement a refresh-token endpoint and tests, or stop clients from attempting token refresh.

## Recommendations

- Implement a refresh-token endpoint and tests, or stop clients from attempting token refresh.
- Add JWT decoding and validation for signature, expiry, token type, issuer, and audience.
- Add tests that distinguish failed login, expired access token, and failed refresh responses.

## Limitations

- Git history was unavailable: configured repository has no .git directory
