# zio - I/O and utility functions

def get_line_groups(lines, nostrip=False):
    '''return list of lists of lines, each separated by empty lines, ignores empty lines from start and end,
    by default also strips all lines (if nostrip is set only strips empty lines)'''
    lines=list(lines)
    lines.append('') # add terminator
    res=[]
    group=[]
    for line in lines:
        line_str=line.strip()
        if nostrip==False or len(line_str)<1:
            line=line_str
        if len(line)>0:
            group.append(line)
        elif len(group)>0: # close group
            res.append(group)
            group=[]
    return res

class StopExecution(Exception):
    def _render_traceback_(self):
        pass

def exit():
    '''stop execution of a notebook cell without any (error) message'''
    raise StopExecution()
