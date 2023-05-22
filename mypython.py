#A few string about this program


import sys
import os
#import logging
import inspect

#logging.basicConfig(format = '%(filename)-5s %(levelname)-8s [%(asctime)s]  %(message)s', level = logging.DEBUG)

__COLOR_SEQUENCES={'red':'91m','yellow':'93m','green':'92m',
'cyan':'96m', 'bold':'01m'}

def __getprogname():
  progname=__name__ + '.py'
  i=2   # i=0 is __getprogname() and i=1 is a function inside this module
  while progname == __name__ + '.py':
    progname=os.path.basename( inspect.getfile(inspect.stack()[i][0]))
    i+=1
  return os.path.basename(progname)
    
    
### Colored printing ###
     
def print_colored_text(text,color):
  try:    #Check the colour is known
    color_code=__COLOR_SEQUENCES[color]
  except KeyError:    #Replace the default message
    raise KeyError('Color \'{}\' is not defined'.format(color))
  start_seq='\033['+__COLOR_SEQUENCES[color]
  end_seq='\033[0m'
  print(start_seq+text+end_seq)
        
def printerr(text,progname=""):
  if not progname: 
    progname=__getprogname()
  print_colored_text('[{}]: Error: {}'.format(progname,text),'red')
          
def printwarn(text,progname=""):
  if not progname: 
    progname=__getprogname()
  print_colored_text('[{}]: Warning: {}'.format(progname,text),'yellow')
        
def printbold(text,progname=""):
  if not progname: 
    progname=__getprogname()
  print_colored_text('[{}]: {}'.format(progname,text),'bold')
        
def printgreen(text,progname=""):
  if not progname: 
    progname=__getprogname()
  print_colored_text('[{}]: {}'.format(progname,text),'green')
        
def printcaption(text,progname=""):
  if not progname: 
    progname=__getprogname()
  print_colored_text('[{}]: {}'.format(progname,text),'cyan')
  
def change_terminal_caption(text):
  print('\33]0;{}\a'.format(text), end='', flush=True)
  
  
###################################

def die(text,progname=""):
  printerr(text,progname)
  sys.exit(1);


####################################

def __do_action(action, text, **kwargs):
  if action == 'nothing':
    return
  elif action == 'die':
    die(text,**kwargs)
  elif action == 'warning':
    printwarn(text,**kwargs)
  elif action == 'exception':
   raise Exception(text)
  else:
    raise KeyError('action \'{}\' is not allowed'.format(action))
    
def check_switching_arguments(argument,list_of_values, with_arg=''):
  if argument not in list_of_values:
    if with_arg:
      raise KeyError('argument value \'{}\' is not allowed together with argument \'{}\''.format(argument,with_arg))
    else:
      raise KeyError('argument value \'{}\' is not allowed.'.format(argument))
    return None
  return  argument
  
def check_keywords_are_allowed(dict_to_test, list_of_keys):
  if len(dict_to_test) == 0:
    raise KeyError('empty dicts is not allowed')
    return False
  for key in dict_to_test.keys():
    if key not in list_of_keys:
      raise KeyError('keyword \'{}\' is not allowed'.format(key))
      return False
  return True
  
# def vars_to_dict(*args):
  # print(args)
  # print(locals())
  
def check_file_exists(filepath, action='exception', progname=''):
  '''Check the file exists and return absolute path. Otherwise it perform
  the 'action' (raise exception by default) and returns None.'''
  if not os.path.exists(filepath):
    __do_action(action, 'File \'{}\' is not found'.format(filepath),progname=progname)
    return None
  return os.path.abspath(filepath)
  
def check_file_not_exist_or_remove(filepath, overwrite=False, action='exception', progname=''):
  '''Returns absolute path is the file does not exists. Otherwise it performs
  the 'action' (raise exception by default) and returns None.'''
    
  if os.path.exists(filepath):
    if overwrite:
      os.remove(filepath)
    else:
      __do_action(action, 'File \'{}\' already exists'.format(filepath),progname=progname)
      return None
  return os.path.abspath(filepath)
      
def check_files_in_list_exist(filelist, datapath='', listtype='ascii', pathtype='', action='exception',progname=''):
  '''Call os.path.exists() for each file in the list. The filelist 
  argument can be the path of an ascii of just a python list. The list 
  can contain absolute or relative paths of files or just filenames in some 
  directry pointed by the 'datapath' argument. The relative paths may
  reffer to the directory containing the listfile (default), to the 
  current word directory or to an arbitrary path provided in the 'datapath'
  argument. Strings starting with '#' will be ignored. The function returns
  list of absolute paths or performs 'action' if an error occures.
  
    listype  = 'ascii' (default) | 'list'
    pathtype = 'rel_list' (default) | 'rel_cwd' | 'rel_path' | 'abs' | 'only_names'
    action = 'die' | 'exception' | 'warning' | 'nothing'
    '''
  check_switching_arguments(listtype,['ascii','list'])
  
  if pathtype:
      check_switching_arguments(pathtype,['rel_list','rel_cwd','rel_path', 'abs','only_names'])
    
  res=[]               #list for result to return
  files_to_check=[]    #list of not commented files  
  if listtype == 'ascii':
    if not pathype:
      if datapath:
        pathtype='rel_path'
      else:
        pathtype='rel_list'
        
    with open(filelist) as fl:    #Read lines from file
      curline=fl.readline().strip()
      while curline:
        if not curline.startswith('#'):
          files_to_check.append(curline) 
        curline=fl.readline().strip()
  else: #listtype == 'list'
    if pathtype:
      check_switching_arguments(pathtype,['rel_cwd','rel_path','abs','only_names'],with_arg='listtype=list')
    else:
      pathtype='rel_path'
    files_to_check=filelist
    
  #Switch pathtype
  if pathtype in ['rel_path', 'only_names' ] and not datapath:
    raise TypeError('pathtype=\'rel_path\' or \'only_names\' requires \'datapath\' argument')
  else:
    datapath=os.path.abspath(datapath)+'/'
  
  if pathtype == 'rel_list':
    datapath=os.path.dirname(os.path.abspath(filelist)) + '/'
  if pathtype == 'rel_cwd':
    datapath=os.getcwd() + '/'
  if pathtype == 'abs':    
    datapath=''
    
  #Trim './' or get only file names
  if pathtype== 'only_names':
    files_to_check = [os.path.basename(x) for x in files_to_check ]
  else:
    files_to_check = [ x[2:] if x.startswith('./') else x for x in files_to_check ]
  
  #Checl files
  for curfile in files_to_check:
    curpath=datapath+curfile
    if os.path.exists(curpath):
      res.append(os.path.abspath(curpath))
    else:
      __do_action(action, 'File \'{}\' is not found'.format(curpath),progname=progname)
    
  return res
        
