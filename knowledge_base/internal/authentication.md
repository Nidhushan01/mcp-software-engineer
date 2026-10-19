# Authentication and token lifecycle

The API issues short-lived JWT access tokens after successful login. Clients must not treat an access token as a refresh token.

## Required refresh behavior

A refresh flow must use a separately issued refresh token. The refresh endpoint must validate the token signature, expiry, issuer, audience, and token type before issuing a new access token. Invalid or expired refresh tokens return HTTP 401.

## Configuration

Token signing and verification must use the same configured secret and algorithm. Production deployments must provide `JWT_SECRET`; the development fallback must never be used in production.

## Testing expectations

Tests must cover successful login, invalid credentials, expired access tokens, valid refresh, expired refresh tokens, and access tokens incorrectly submitted to the refresh endpoint.
