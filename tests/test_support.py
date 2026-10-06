"""Use a temporary bootstrap for module-level app initialization in tests."""
import atexit,os,tempfile
bootstrap=tempfile.TemporaryDirectory(prefix='leafread-test-bootstrap-')
# Never initialize an existing user database through inherited service config.
os.environ['APP_DATA_DIR']=bootstrap.name
atexit.register(bootstrap.cleanup)
