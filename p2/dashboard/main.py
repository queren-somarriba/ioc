import uvicorn
from fastapi import FastAPI

from nicegui import app, ui


fastapi_app = FastAPI()
@fastapi_app.get("/")
def root():
	return {'message': 'Hello! Browse to /gui to see the NiceGUI app.'}

@ui.page('/')
def show():
	ui.label('Hello, NiceGUI!')

	ui.dark_mode().bind_value(app.storage.user, 'dark_mode')
	ui.checkbox('dark_mode').bind_value(app.storage.user, 'dark_mode')


ui.run_with(
	fastapi_app,
	mount_path='/gui',
	storage_secret='pick your private secret here'
)

if __name__ == '__main__':
	uvicorn.run('main:fastapi_app', log_level='info', reload=True)
