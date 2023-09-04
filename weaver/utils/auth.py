import json
import logging
import os
import time
import urllib.request
from typing import Dict, List
from ..config import logger
from jose import jwk, jwt
from jose.utils import base64url_decode
from pydantic import BaseModel
from requests import get
from fastapi import Request, Depends, HTTPException, status


class JWK(BaseModel):
    """A JSON Web Key (JWK) model that represents a cryptographic key.

    The JWK specification:
    https://datatracker.ietf.org/doc/html/rfc7517
    """

    alg: str
    e: str
    kid: str
    kty: str
    n: str
    use: str


class CognitoAuthenticator:
    def __init__(self, pool_region: str = os.environ.get("AWS_COGNITO_REGION"), 
                 pool_id: str = os.environ.get("AWS_USER_POOL_ID"), 
                 client_id: str = os.environ.get("AWS_USER_POOL_CLIENT_ID")) -> None:
        self.pool_region = pool_region
        self.pool_id = pool_id
        self.client_id = client_id
        self.issuer = f"https://cognito-idp.{self.pool_region}.amazonaws.com/{self.pool_id}"
        self.jwks = self.__get_jwks()

    def __get_jwks(self) -> List[JWK]:
        """Returns a list of JSON Web Keys (JWKs) from the issuer. A JWK is a
        public key used to verify a JSON Web Token (JWT).

        Returns:
            List of keys
        Raises:
            Exception when JWKS endpoint does not contain any keys
        """

        res = get(f"{self.issuer}/.well-known/jwks.json").json()
        if not res.get("keys"):
            raise Exception("The JWKS endpoint does not contain any keys")
        jwks = [JWK(**key) for key in res["keys"]]
        return jwks

    def verify_token(self, token: str) -> Dict:
        """Verify a JSON Web Token (JWT) and return its claims.

        For more details refer to:
        https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html

        Args:
            token: The token to verify
        Returns:
            A dict representation of the token claims if valid, None otherwise
        """
        try:
            self._is_jwt(token)
            self._get_verified_header(token)
            claims = self._get_verified_claims(token)
        except CognitoError as e:
            logger.error(f"Error verifying token: {e}")
            return None
        return claims

    def _is_jwt(self, token: str) -> bool:
        """Validate a JSON Web Token (JWT).
        A JSON Web Token (JWT) includes three sections: Header, Payload and
        Signature. They are base64url encoded and are separated by dot (.)
        characters. If JWT token does not conform to this structure, it is
        considered invalid.

        Args:
            token: The token to validate
        Returns:
            True if valid
        Raises:
            CognitoError when invalid token
        """

        try:
            jwt.get_unverified_header(token)
            jwt.get_unverified_claims(token)
        except jwt.JWTError as e:
            logger.warning(f"Invalid JWT: {e}")
            raise InvalidJWTError
        return True

    def _get_verified_header(self, token: str) -> Dict:
        """Verifies the signature of a a JSON Web Token (JWT) and returns its
        decoded header.

        Args:
            token: The token to decode header from
        Returns:
            A dict representation of the token header
        Raises:
            CognitoError when unable to verify signature
        """

        # extract key ID (kid) from token
        headers = jwt.get_unverified_header(token)
        kid = headers["kid"]

        # find JSON Web Key (JWK) that matches kid from token
        key = next((jwk.construct(k.dict()) for k in self.jwks if k.kid == kid), None)
        if not key:
            logger.warning(f"Unable to find a signing key that matches '{kid}'")
            raise InvalidKidError

        # get message and signature (base64 encoded)
        message, encoded_signature = str(token).rsplit(".", 1)
        signature = base64url_decode(encoded_signature.encode("utf-8"))

        if not key.verify(message.encode("utf8"), signature):
            logger.warning("Signature verification failed")
            raise SignatureError

        # signature successfully verified
        return headers

    def _get_verified_claims(self, token: str) -> Dict:
        """Verifies the claims of a JSON Web Token (JWT) and returns its claims.

        Args:
            token: The token to decode claims from
        Returns:
            A dict representation of the token claims
        Raises:
            CognitoError when unable to verify claims
        """

        claims = jwt.get_unverified_claims(token)

        # verify expiration time
        if claims["exp"] < time.time():
            logger.warning("Expired token")
            raise TokenExpiredError

        # verify issuer
        if claims["iss"] != self.issuer:
            logger.warning("Invalid issuer claim")
            raise InvalidIssuerError

        # verify audience
        # note: claims["client_id"] for access token, claims["aud"] otherwise
        if claims.get("client_id", claims.get("aud")) != self.client_id:
            logger.warning("Invalid audience claim")
            raise InvalidAudienceError

        # verify token use
        if claims["token_use"] != "id":
            logger.warning("Invalid token use claim")
            raise InvalidTokenUseError

        # claims successfully verified
        return claims


class CognitoError(Exception):
    def __init__(self, message):
        self.message = message
        logger.warning(self.message)
        super().__init__(self.message)


class InvalidJWTError(CognitoError):
    def __init__(self):
        super().__init__("Invalid JWT")


class InvalidKidError(CognitoError):
    def __init__(self):
        super().__init__("Unable to find a signing key that matches 'kid'")


class SignatureError(CognitoError):
    def __init__(self):
        super().__init__("Signature verification failed")


class TokenExpiredError(CognitoError):
    def __init__(self):
        super().__init__("Expired token")


class InvalidIssuerError(CognitoError):
    def __init__(self):
        super().__init__("Invalid issuer claim")


class InvalidAudienceError(CognitoError):
    def __init__(self):
        super().__init__("Invalid audience claim")


class InvalidTokenUseError(CognitoError):
    def __init__(self):
        super().__init__("Invalid token use claim")

def get_cognito_authenticator() -> CognitoAuthenticator:
    return CognitoAuthenticator()

def get_auth(request: Request, authenticator: CognitoAuthenticator = Depends(get_cognito_authenticator)):
    auth_header = request.headers.get('Authorization')
    if auth_header:
        token = auth_header.split(' ')[1]  # extract the JWT token
        claims = authenticator.verify_token(token)
        if claims is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return claims
    else:
        raise HTTPException(status_code=401, detail="Missing Authorization header")