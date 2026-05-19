import os
import uuid
import aiofiles
import httpx
from datetime import datetime
from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from jose import jwt
from dotenv import load_dotenv

load_dotenv()

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
ADMIN_DISCORD_ID = os.getenv("ADMIN_DISCORD_ID")

os.makedirs("static/uploads", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app = FastAPI(docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

engine = create_engine('sqlite:///chetspy.db', connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Evidence(Base):
    __tablename__ = "evidences"
    id = Column(Integer, primary_key=True, index=True)
    author_name = Column(String)
    discord_id = Column(String)
    suspect_name = Column(String)
    faction = Column(String)
    material_link = Column(String)
    description = Column(Text)
    photo_path = Column(String)
    status = Column(String, default="Ожидает")
    case_link = Column(String, nullable=True)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    discord_id = Column(String, primary_key=True, index=True)
    username = Column(String)
    role = Column(String, default="user") # user, check, full

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_token(discord_id: str, role: str):
    return jwt.encode({"sub": discord_id, "role": role}, SECRET_KEY, algorithm="HS256")

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user = db.query(User).filter(User.discord_id == payload.get("sub")).first()
        return user
    except:
        return None

def require_role(allowed_roles: list):
    async def role_checker(user: User = Depends(get_current_user)):
        if not user or user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Доступ запрещен. Недостаточно прав.")
        return user
    return role_checker

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    return templates.TemplateResponse(request=request, name="404.html", context={})

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request=request, name="index.html", context={"user": user})

@app.get("/login")
async def login():
    url = f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri={DISCORD_REDIRECT_URI}&response_type=code&scope=identify"
    return RedirectResponse(url)

@app.get("/auth/callback")
async def auth_callback(code: str, db: Session = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        token_res = await client.post("https://discord.com/api/oauth2/token", data={
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DISCORD_REDIRECT_URI
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})
        
        token_data = token_res.json()
        if "access_token" not in token_data:
            return RedirectResponse("/")

        user_res = await client.get("https://discord.com/api/users/@me", headers={
            "Authorization": f"Bearer {token_data['access_token']}"
        })
        user_data = user_res.json()

    discord_id = user_data["id"]
    db_user = db.query(User).filter(User.discord_id == discord_id).first()
    
    role = "full" if discord_id == ADMIN_DISCORD_ID else "user"
    
    if not db_user:
        db_user = User(discord_id=discord_id, username=user_data["username"], role=role)
        db.add(db_user)
        db.commit()
    elif discord_id == ADMIN_DISCORD_ID and db_user.role != "full":
        db_user.role = "full"
        db.commit()

    token = create_token(discord_id, db_user.role)
    response = RedirectResponse("/form")
    response.set_cookie(key="session", value=token, httponly=True)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse("/")
    response.delete_cookie("session")
    return response

@app.get("/form", response_class=HTMLResponse)
async def form_page(request: Request, file: str = None, user: User = Depends(get_current_user)):
    file_url = None
    if file:
        base_url = str(request.base_url).rstrip("/")
        file_url = f"{base_url}/static/uploads/{file}"
    return templates.TemplateResponse(request=request, name="form.html", context={"user": user, "file_url": file_url})

@app.post("/submit")
async def submit_evidence(
    request: Request,
    suspect_name: str = Form(...),
    faction: str = Form(...),
    material_link: str = Form(...),
    description: str = Form(...),
    photo: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user:
        author = user.username
        discord_identifier = f"<@{user.discord_id}>"
        u_id = user.discord_id
    else:
        author = "Анонимный детектив"
        discord_identifier = "Не авторизован"
        u_id = "N/A"

    file_ext = photo.filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{file_ext}"
    file_path = f"static/uploads/{filename}"
    
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await photo.read()
        await out_file.write(content)

    base_url = str(request.base_url).rstrip("/")
    absolute_photo_url = f"{base_url}/{file_path}"

    evidence = Evidence(
        author_name=author,
        discord_id=u_id,
        suspect_name=suspect_name,
        faction=faction,
        material_link=material_link,
        description=description,
        photo_path=f"/{file_path}"
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    async with httpx.AsyncClient() as client:
        embed = {
            "title": "📁 Новые материалы в реестре",
            "color": 3447003,
            "fields": [
                {"name": "Агент", "value": f"{author} ({discord_identifier})", "inline": True},
                {"name": "Субъект", "value": suspect_name, "inline": True},
                {"name": "Фракция", "value": faction, "inline": True},
                {"name": "Сводка", "value": description, "inline": False},
                {"name": "Материалы", "value": f"[Источник]({material_link})", "inline": True},
                {"name": "Фотоотчет", "value": f"[Открыть снимок]({absolute_photo_url})", "inline": True}
            ],
            "image": {
                "url": absolute_photo_url
            }
        }
        await client.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})

    return RedirectResponse(f"/form?file={filename}", status_code=303)

@app.get("/table", response_class=HTMLResponse)
async def table_page(request: Request, db: Session = Depends(get_db), user: User = Depends(require_role(["check", "full"]))):
    evidences = db.query(Evidence).order_by(Evidence.id.desc()).all()
    return templates.TemplateResponse(request=request, name="table.html", context={"evidences": evidences, "user": user})

@app.post("/update_evidence/{ev_id}")
async def update_evidence(
    ev_id: int, 
    status: str = Form(...), 
    case_link: str = Form(""), 
    comments: str = Form(""), 
    db: Session = Depends(get_db), 
    user: User = Depends(require_role(["check", "full"]))
):
    ev = db.query(Evidence).filter(Evidence.id == ev_id).first()
    if ev:
        ev.status = status
        ev.case_link = case_link
        ev.comments = comments
        db.commit()
    return RedirectResponse("/table", status_code=303)

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(get_db), user: User = Depends(require_role(["full"]))):
    users = db.query(User).all()
    return templates.TemplateResponse(request=request, name="admin.html", context={"users": users, "user": user})

@app.post("/admin/update_role/{user_id}")
async def update_role(user_id: str, role: str = Form(...), db: Session = Depends(get_db), user: User = Depends(require_role(["full"]))):
    target_user = db.query(User).filter(User.discord_id == user_id).first()
    if target_user and target_user.discord_id != ADMIN_DISCORD_ID:
        target_user.role = role
        db.commit()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/delete_evidence/{ev_id}")
async def delete_evidence(ev_id: int, db: Session = Depends(get_db), user: User = Depends(require_role(["full"]))):
    ev = db.query(Evidence).filter(Evidence.id == ev_id).first()
    if ev:
        file_to_del = ev.photo_path.lstrip("/")
        if os.path.exists(file_to_del):
            os.remove(file_to_del)
        db.delete(ev)
        db.commit()
    return RedirectResponse("/table", status_code=303)