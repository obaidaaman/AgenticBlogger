
from core.models.models import SignUpModel, LoginModel
from datetime import timedelta, datetime, timezone
import jwt
from fastapi import Request, HTTPException
import os
db :list = []


def signup(body: SignUpModel):
    for user in db:
        if user["username"] == body.username:
            raise HTTPException(status_code=400, detail="User already exists")
    db.append({
        "username" : body.username,
        "password" : body.password,
        "email": body.email
    })

    return {
        "status" : 200,
        "message" : "User added successfully"
    }


def login(body : LoginModel):
    username = body.username
    password = body.password

    for user in db:
        if user.get("username") == username and user.get("password") == password:
            token_data = {
                "username" : user.get("username"),
                
                "email" :  user.get("email"),
                "exp" : datetime.now(timezone.utc) + timedelta(hours=24)

            }
            token = jwt.encode(token_data, os.getenv("SECRET_KEY"), algorithm=os.getenv("ALGORITHM"))
            return {
                "status" : 200,
                "token" : token
            }
    raise HTTPException(status_code=401, detail="User not found")
        
    
           



def is_authenticated(request: Request):
    token = request.headers.get("authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Token Not Found")
    token = token.split(" ")[-1]
    try:
        data = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=[os.getenv("ALGORITHM")])
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid Token")
    username = data.get("username")
    email = data.get("email")
    return {
        "status" : 200,
        "username" : username,
        "email" : email
    }
    