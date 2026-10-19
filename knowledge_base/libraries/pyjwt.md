# PyJWT API reference

Library: PyJWT

## `jwt.encode()`

Creates a signed JSON Web Token from claims, a signing key, and an algorithm.

## `jwt.decode()`

Validates and decodes a token. Callers should provide an explicit algorithm allow-list and validate application-required claims such as expiry, issuer, audience, and token type.

Decoding payload data without signature verification must not be used for authentication decisions.
