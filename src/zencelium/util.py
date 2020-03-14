import datetime


def timestamp():
    return datetime.datetime.utcnow().isoformat()


def add_space_to_meta(frame, space_name, space_uuid):
    space_meta = {'space': {
        # 'uuid': space_uuid, 
        'name': space_name
        }}
    if frame._meta:
        frame._meta.update(space_meta)
    else:
        frame._meta = space_meta

def clean_space_names(self, space_names):
    if not space_names:
        return set()
    if isinstance(space_names, str):
        space_names = {s.strip() for s in space_names.split(',')}
    else:
        space_names = set(space_names)
    return space_names
