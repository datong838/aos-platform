"""One original native migration step on an explicitly bound isolated cluster."""
import os,sys,json

def require_step(step,cluster,actual_cluster,db,version,server_addr):
 if type(step) is not int or step not in (158,159):raise ValueError('FIXED_ORIGINAL_STEP_REQUIRED')
 if not isinstance(cluster,str) or not cluster.isdigit() or actual_cluster!=cluster:raise ValueError('CLUSTER_IDENTITY_DRIFT')
 if db!='aos_current_preview_20260927' or version!='a0v_'+str(step-1) or server_addr is not None:raise ValueError('EXACT_PREVIOUS_UNIX_DATABASE_REQUIRED')

def main():
 import psycopg
 from sqlalchemy import create_engine
 from alembic.config import Config
 from alembic import command
 from alembic.script import ScriptDirectory
 assert len(sys.argv)==3 and sys.argv[1] in ('158','159')
 assert not os.environ.get('AOS_DATABASE_URL')
 os.environ['AOS_DOTENV_DISABLED']='1';sys.path.insert(0,'/code/services/aos-api')
 config=Config('/code/services/aos-api/alembic.ini');config.set_main_option('script_location','/code/services/aos-api/alembic');assert ScriptDirectory.from_config(config).get_heads()==['a0v_159']
 step=int(sys.argv[1]);cluster=sys.argv[2]
 engine=create_engine('postgresql+psycopg://aos_app@/aos_current_preview_20260927?host=/pgsocket')
 try:
  with engine.begin() as connection:
   raw=connection.connection.driver_connection
   identity=raw.execute('SELECT system_identifier::text,current_database(),inet_server_addr() FROM pg_control_system()').fetchone()
   versions=raw.execute('SELECT version_num FROM public.alembic_version').fetchall();assert len(versions)==1
   require_step(step,cluster,identity[0],identity[1],versions[0][0],identity[2])
   config.attributes['connection']=connection;command.upgrade(config,'a0v_'+str(step))
   assert raw.execute('SELECT version_num FROM public.alembic_version').fetchall()==[('a0v_'+str(step),)]
  print(json.dumps({'status':'ORIGINAL_NATIVE_ALEMBIC_STEP_COMMIT_CONFIRMED','step':step,'version':'a0v_'+str(step),'cluster':cluster,'unix_socket':True,'business_execution':False}),flush=True)
 finally:engine.dispose()
if __name__=='__main__':main()
