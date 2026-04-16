
from pwdlib import PasswordHash
from pymongo.errors import DuplicateKeyError
from core.models.models import SignUpModel, LoginModel
from datetime import timedelta, datetime, timezone
import jwt
from fastapi import Request, HTTPException, status
import os
db :list = []
password_hash = PasswordHash.recommended()



def get_password_hash(password):
    return password_hash.hash(password)


def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)

async def signup(req: Request, body: SignUpModel):
    
    hashed_password = get_password_hash(body.password)
    
    
    user_document = {
        "username": body.username,
        "email": body.email,
        "password": hashed_password,
    }

    try:
        
        current_user = await req.app.state.database["users"].insert_one(user_document)
        
    except DuplicateKeyError:
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Username or email already registered"
        )
    except Exception as e:
        
        req.app.state.logger.error(f"Signup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Something went wrong: " + str(e)
        )
    req.app.state.logger.info(f"New user registered: {body.username}")
    
    return {
        "id" : str(current_user.inserted_id),
        "status": 201,
        "message": "User added successfully",

    }
    


async def login(req: Request, body : LoginModel):
    username = body.username
    password = body.password
    try:
        user = await req.app.state.database["users"].find_one({
            "username" : username,
        })

        if not user or not verify_password(password,user.get("password")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

        token_data ={
            "sub" : user.get("username"),
            "email" :  user.get("email"),
            "exp" : datetime.now(timezone.utc) + timedelta(hours=24)
        }
    
        token = jwt.encode(token_data, os.getenv("SECRET_KEY"), algorithm=os.getenv("ALGORITHM"))
        return {
                "status" : 200,
                "access_token" : token,
                "token_type" : "bearer"
            }
    except HTTPException:
        raise
    except Exception as e:
        req.app.state.logger.error(f"Login error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Something went wrong" )
    
        
    
           



def is_authenticated(request: Request):
    token = request.headers.get("authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Token Not Found")
    token = token.split(" ")[-1]
    try:
        data = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=[os.getenv("ALGORITHM")])
    except Exception as e:
        request.app.state.logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Invalid Token")
    username = data.get("sub")
    email = data.get("email")
    return {
        "status" : 200,
        "username" : username,
        "email" : email
    }
    