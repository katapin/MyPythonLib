"""Methods to perform basic checks like existence of input files and so on.""" 


import sys, os, time
from enum import StrEnum, auto
import functools, inspect, subprocess

#logging.basicConfig(format = '%(filename)-5s %(levelname)-8s [%(asctime)s]  %(message)s', level = logging.DEBUG)

####Teminal output and colored printing ##############

__COLOR_SEQUENCES={'red':'91m','yellow':'93m','green':'92m',
'cyan':'96m', 'bold':'01m'}

def _print_colored(text, color):
    print('\033['+__COLOR_SEQUENCES[color]+text+'\033[0m')

def print_colored_text(text, color):
    """Color the output."""
    if color not in __COLOR_SEQUENCES:    #Check the colour is known
        raise KeyError("Color '{}' is not defined".format(color))
    _print_colored(text, color)
    
def set_logfile(path:str, append:bool=False):
    if path != None:
        if append==False and os.path.exists(path):
            raise OSError(f"Can't create '{path}', the file already exists.")
        _LoggerStatic.open_logfile(path)
    else:
        _LoggerStatic.close_logfile()
    
class _LoggerStatic():
    __flogfile=None
        
    @classmethod
    def open_logfile(cls, path):
        cls.close_logfile()
        is_exists = os.path.exists(path)
        cls.__flogfile = open(path, 'a')
        if is_exists:
            cls.__flogfile.write('\n')
        
    @classmethod 
    def close_logfile(cls):
        if cls.__flogfile:
            cls.__flogfile.close()
            cls.__flogfile=None
            
    @classmethod            
    def _call_popen(cls, cmd, stdin, catch_output):
        if catch_output:
            child=subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT, 
                   stdout=subprocess.PIPE, stdin=subprocess.PIPE, universal_newlines=True)
            child.stdin.write(stdin)  
            child.stdin.flush()                       
            child.stdin.close()
            for line in child.stdout:
                print(line.strip())
                cls.__flogfile.write(line)
            cls.__flogfile.flush()
        else:
            child=subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT, 
                   stdin=subprocess.PIPE, universal_newlines=True)
            child.stdin.write(stdin)  
            child.stdin.flush()                       
            child.stdin.close()
        child.wait() 
        return child
            
    @classmethod
    def callandlog(cls, cmd, stdin='', separate_logfile='', extra_start='',
                   extra_end='', return_code=False, progname=None):
        cls.print_colored_and_log(cmd, progname, color='bold')
        command = extra_start + cmd + extra_end
        if separate_logfile:
            command = 'set -o pipefail; '+command+' | tee -a '+separate_logfile
            cls.onlylog(f"See log in '{separate_logfile}'", progname=None)
            child = cls._call_popen(command, stdin, False)
        elif cls.__flogfile:
            child = cls._call_popen(command, stdin, True)
        else:
            child = cls._call_popen(command, stdin, False)
        
        code=child.returncode
        if code == 0:
            cls.print_colored_and_log(f"Finished with code {code}", progname, color='bold')
        else:
            cls.print_colored_and_log(f"Finished with code {code}", progname, 
                  msgtype='Warning:', color='yellow')
            
        if return_code:
            return bool(not code), code
        
        return bool(not code)
    
    @staticmethod
    def __prepare_text(text, progname=None, msgtype=''):
        if progname == None: 
            progname = _getprogname()
        progtxt = f'[{progname}]:' if progname else ''
        return ' '.join([x for x in [progtxt, msgtype, text] if x])
    
    @classmethod
    def __log_text(cls, text):
        if cls.__flogfile:
            timestamp = time.strftime('%Y %b %d %H:%M:%S', time.localtime())
            cls.__flogfile.write(timestamp+' - '+text+'\n')
            cls.__flogfile.flush()
            
    @classmethod    
    def onlylog(cls, text, progname=None, msgtype=''):
        _text = cls.__prepare_text(text, progname, msgtype)
        cls.__log_text(_text)
    
    @classmethod
    def print_colored_and_log(cls, text, progname=None, msgtype='', color=None):
        _text = cls.__prepare_text(text, progname, msgtype)
        if color:
            _print_colored(_text, color)
        else:
            print(_text)
        cls.__log_text(_text)
        return text

#Create functons with names 'print+color' and add them into namespace  
#They return the printed text to pass it to Exception message      
printred, printyellow, printcyan = None, None, None  #To not show 'Undefined name' error below
for color in __COLOR_SEQUENCES:
    locals()['print'+color] = functools.partial(_LoggerStatic.print_colored_and_log, color=color)
printandlog = functools.partial(_LoggerStatic.print_colored_and_log, color=None)
printerr  = functools.partial(printred, msgtype='Error:')     
printwarn = functools.partial(printyellow, msgtype='Warning:')   
printcaption = printcyan
logtext = _LoggerStatic.onlylog
callandlog = _LoggerStatic.callandlog

def die(text, progname=None):
    printerr(text, progname)
    sys.exit(1);
  
def change_terminal_caption(text):
    print('\33]0;{}\a'.format(text), end='', flush=True)
     

#### Some functions and classes for internal use #################

class Action(StrEnum):
    """Enum of allowed Action which can be used in checks."""
    
    DIE       = auto()
    ERROR     = auto()
    WARNING   = auto()
    EXCEPTION = auto()
    NOTHING   = auto()

def _do_action(action:Action, text, progname=None, exception_class=Exception):
    if action == Action.NOTHING:
        return
    elif action == Action.DIE:
        die(text, progname)
    elif action == Action.WARNING:
        printwarn(text, progname)
    elif action == Action.ERROR:
        printerr(text, progname)
    elif action == Action.EXCEPTION:
        raise exception_class(text)
    else:
        raise KeyError("action '{}' is not allowed".format(action))
        
def _getprogname():

    modulename=__name__ + '.py'
    progname='_'
    i=2   # i=0 is _getprogname() and i=1 is a function inside this module
    stack=inspect.stack()
    while modulename in (__name__ + '.py', 'functools.py') or progname[0] == '_':
        modulename=os.path.basename(stack[i][1])
        progname = stack[i][3]
        i+=1
    return modulename if progname == '<module>' else progname
        
def getownname():
    """Return the name of the function that calls this.""" 
    return inspect.stack()[1][3]
    
def _check_option_is_allowed(argument:str, allowed_values:list, with_arg=''):
    """Check if argument is valid or raise KeyError.""" 
    if argument not in allowed_values:
        if with_arg:
            raise KeyError("argument value '{}' is not allowed together with argument '{}'".format(argument,with_arg))
        else:
            raise KeyError("argument value '{}' is not allowed.".format(argument))
    return True
  
def _check_keywords_are_allowed(dict_to_test:dict, allowed_keys:list):
    """Check keyword of the dict are valid or raise KeyError."""
    if len(dict_to_test) == 0:
        raise KeyError('empty dicts is not allowed')
    for key in dict_to_test.keys():
        if key not in allowed_keys:
            raise KeyError("keyword '{}' is not allowed".format(key))
    return True

def _read_ascii(ascii_path:str, comment_symbol:str='#') -> list:
    """Save content from ascii file to python list."""
    lines=[]
    with open(ascii_path) as fl:    #Read lines from file
        for line in fl:
            stripped = line.strip()
            if not stripped.startswith(comment_symbol):
                lines.append(stripped) 
    return lines

#### Classes for manipultaion with file paths ####

class FilePath(str):
    """Class to help dealing with file names."""
    
    def __new__(cls, path:str):
        if not path:
            raise ValueError('Path cannot be empty')
        path=os.path.normpath(path)
        if path[0] == '/' and cls == FilePath:
            instance = super().__new__(_FilePathAbs, path)
        else:
            instance = super().__new__(cls, path)
        return instance
    
    def __init__(self, path:str):

        self.__isabs = True if self[0] == '/' else False
        dirname = os.path.dirname(self)
        self.__dirname = dirname or '.'
        self.__basename=os.path.basename(self)
        
    @classmethod
    def _from_basename_and_dirname(cls, basename, dirname):
        if dirname[-1] == '/': dirname = dirname[:-1]  
        return FilePath(f'{dirname}/{basename}')
        
    @property
    def dirname(self):
        """Returns the directory component of the path."""
        return self.__dirname
    
    @property
    def basename(self):
        """Returns the finename component of a full path."""
        return self.__basename

    @property
    def isabs(self):
        """Returns True if the path is absolure."""
        return self.__isabs
    
    @property
    def str(self):
        """Convert to ordinar string"""
        return str(self)
        
    def __radd__(self, other):
        if type(other) != str:
            raise TypeError('Only string can be attached.')
        return FilePath(other+str(self))
    
    def replace_basename(self, text:str):
        """Return a new Filepath object with another basename."""
        return self._from_basename_and_dirname(text, self.__dirname)
        
    def replace_dirname(self, text:str):
        """Return a new Filepath object with another dirname."""
        dirname = text or '.'
        return self._from_basename_and_dirname(self.__basename, dirname)
    
    def make_absolute(self):
        """Add CWD to the file path to make it absolute."""
        if not self.__isabs:
            return self._from_basename_and_dirname(self.__basename, 
                   os.getcwd()+'/'+self.__dirname)
        else:
            return self
             
    def starts_with(self, text:str):
        """Append string to the star of the filename."""
        return self._from_basename_and_dirname(f'{text}{self.__basename}', self.__dirname)
    
    def ends_with(self, text:str):
        """Append string to the end of the filename (before extension)."""
        split = os.path.splitext(self.__basename)
        return self._from_basename_and_dirname('{0}{2}{1}'.format(*split,text), 
                                               self.__dirname)
    def add_extension(self, text:str):
        """Add another extension to the existing filepath."""
        return self._from_basename_and_dirname('{}.{}'.format(self.__basename,text), 
                                               self.__dirname)
    def replace_extension(self, text:str):
        """Replace extension of the existing filepath."""
        split = os.path.splitext(self.__basename)
        if text=='':
            return self._from_basename_and_dirname(split[0], self.__dirname)
        if text[0] == '.':
           text = text[1:] if len(text)>1  else ''
        return self._from_basename_and_dirname('{}.{}'.format(split[0],text), 
                                               self.__dirname)
    
class _FilePathAbs(FilePath):  #You shouldn't call this manually
    """Extension of the FilePath class for absolute paths."""  
    
    def file_exists(self):
        return os.path.exists(self)
    
    def file_create(self):
        with open(self,'x'):
            pass
        
    def file_remove(self):
        """Remove the file if it exists."""
        if self.file_exists():
            os.remove(self)
    
class TempFile(_FilePathAbs):
    """Class for manipulation tempfiles' names."""
    
    __files=[]
    __preserved=[]
    
    nameroot='tmp{:d}_'.format(os.getpid())
    
    def __new__(cls, path:str):  #Any path will be convertued to absolute 
        tmpobj = FilePath(path).make_absolute()
        if os.path.isdir(tmpobj):
            raise OSError(f"Can't use path occupied by an existing folder ('{tmpobj}')")
        try:    #Check whether the path is valid and directory is writable
            testfile=tmpobj.replace_basename('tst{}_{}'.format(os.getpid(),time.time_ns()))
            testfile.file_create()
            testfile.file_remove()
        except Exception:
            raise OSError(f"Path '{tmpobj}' is not valid or the host directory is not writable")
        instance = super().__new__(cls, tmpobj)
        instance.__strpath = tmpobj.str
        return instance
        
    def __init__(self, path:str):
        path = self.__strpath
        super().__init__(path)
        self.__files.append(path)
        self.__preserve=False
        
    def __del__(self): 
        """Remove the file when the object is being deleted."""
        if not self.__preserve:
            self.__files.remove(self.__strpath)
            self.file_remove()
            
    @property
    def preserve(self):
        """Turn off automatic removing of the file."""
        return self.__preserve
    
    @preserve.setter 
    def preserve(self, val:bool):
        if val != self.__preserve:
            if val == True:
                self.__files.remove(self.__strpath)
                self.__preserved.append(self.__strpath)
            elif val == False:
                self.__preserved.remove(self.__strpath)
                self.__files.append(self.__strpath)
            else:
                raise TypeError('Must be bool value')
                
    @classmethod
    def generate_from(cls, text:str, new_extension:str=None, hidden:bool=True, unique:bool=False):
        """Generate the name of a tempfile baseed on text."""
        prefix = '.' if hidden else ''
        prefix += str(cls.nameroot)      
        prefix += '{}_'.format(hex(time.time_ns())) if unique else ''
        pathobj = FilePath(text)
        if new_extension != None: pathobj = pathobj.replace_extension(new_extension)
        return cls(pathobj.dirname+'/'+prefix+pathobj.basename)
    
    @classmethod 
    def generate(cls, extension='.tmp', hidden:bool=True):
        """Generate an unique name."""
        text = str(hex(time.time_ns())) + str(extension)
        return cls.generate_from(text, hidden=hidden, unique=False)
            
    @classmethod
    def cleanup(cls):
        """Force removing all the created files. Should be used only with atexit and such."""
        for item in cls.__files:
            if os.path.exists(item):
                os.remove(item)

class ListofPaths(list):
    """Class to operate with lists of files to be processed."""
    
    def __init__(self, list_of_paths:list, basepath:str=None):
        if basepath: basepath = basepath.strip()
        if basepath:
            super().__init__([FilePath(f'{basepath}/{x}') for x in list_of_paths])
        else:
            super().__init__([FilePath(x) for x in list_of_paths])
        
    @classmethod
    def from_ascii(cls, ascii_path:str, basepath=None, comment_symbol='#'):
        """Load list of an ascii file."""
        if basepath == None:
            basepath = os.path.dirname(ascii_path)
        return cls(_read_ascii(ascii_path, comment_symbol),basepath)
    
    def append_left(self, text:str):
        """Append path to the parent directory."""
        return type(self)(self, text)
    
    def append_right(self, text:str):
        """Append path to the parent directory."""
        return type(self)([x+text for x in self])
    
    def only_names(self):
        """Get only file names, remove dirnames."""
        return type(self)([x.basename for x in self])
    
#### Helper functions for user scripts' arguments checks ################    


def check_file_exists(filepath:str, action:Action=Action.DIE, progname:str=None):
    """Check if the file exists and return its absolute path.
    
    It returns absolute path of the file or performs the 'action' (raise exception
    by default) and returns None if the file doesn't exist.
    """
    pathobj = FilePath(os.path.abspath(filepath))
    if not pathobj.file_exists():
        _do_action(action, f"File '{filepath}' is not found",progname=progname, exception_class=FileNotFoundError)
        return None
    return pathobj
  
def check_file_not_exist_or_remove(filepath:str, overwrite:bool=False, 
        action:Action=Action.DIE, extra_text='', progname:str=None, 
        remove_warning:bool=True, exception_class=OSError):
    """Check if the file doesn't exist to further create it.
    
    Return absolute path if the file doesn't exist or if it's allowed to be overwrite it.
    If the option 'overwrite' is True, the existing file will be removed. 
    Otherwise it performs the 'action' (raise exception by default) and returns None.
    

    Parameters
    ----------
    filepath : str | FilePath
        Path to file to check.
    overwrite : bool, optional
        If True, existing file will be removed. The default is False.
    action : Action, optional
        Perform the Action if file exists and can't be removed. The default is Action.EXCEPTION.
    extra_text : str
        Additional text for the message
    progname : str, optional
        Progname to print message. The default is ''.
    remove_warning : bool, optional
        Print warning if file exists but it's allowed to delete it. The default is True.
    exception_class : Exception
        Exception class for Action.EXCEPTION. The default is OSError

    Returns
    -------
    pathobj : FilePath
        DESCRIPTION.

    """
    pathobj = FilePath(filepath).make_absolute()
    if pathobj.file_exists():
        if overwrite:
            os.remove(filepath)
            if remove_warning:
                printwarn(f"File '{filepath}' will be replaced", progname=progname)
        else:
            _do_action(action, f"File '{filepath}' already exists. "+extra_text, 
                progname=progname, exception_class=exception_class)
            return None
    return pathobj
      
@functools.singledispatch
def check_files_in_list_exist(filelist, basepath:str=None, 
        action:Action=Action.DIE, progname=None):
    """Call os.path.exists() for each file in the list.
    
    The filelist argument can be the path of an ascii file, a ListofPaths object
    or just a python list. The list can contain absolute or relative paths and 
    also can be augmented with 'basepath' argument. If the input is an ascii
    file, the relative paths are assumed to refer to the folder that owns 
    the ascii file; strings starting with '#' will be ignored. The function returns 
    the ListofPaths object with absolute paths or performs 'action' if 
    an error occures.
    """
    raise TypeError("Unsupported type {} of 'filelistobj' argument".format(type(filelist)))
    
@check_files_in_list_exist.register(list)
def _list_check_files_in_list_exist(filelist, basepath:str=None, 
         action:Action=Action.DIE, progname=None):
    listobj = ListofPaths(filelist, basepath)
    good_files, bad_files = [], []
    for item in listobj:
        if os.path.exists(item):
            good_files.append(os.path.abspath(item))
        else:
            bad_files.append(item)
    if len(bad_files)>0:
        _do_action(action, "File '{}' ({:d} of {:d} in total) is not found".format(bad_files[0],
            len(bad_files), len(listobj)), progname=progname, exception_class=FileNotFoundError)
        return None
    return ListofPaths(good_files)
    
@check_files_in_list_exist.register(str)
def _str_check_files_in_list_exist(filelist, basepath:str=None, 
          action:Action=Action.DIE, progname=None):
    listobj = ListofPaths.from_ascii(filelist, basepath)
    return _list_check_files_in_list_exist(listobj, action=action, progname=progname)

#### Exception classes

class TaskError(Exception):
    """Exception to raise in custrom scripts."""
    
    def __init__(self, taskname, custom_message=None, filename=''):
        self.taskname = taskname
        if custom_message:
            self.msg = custom_message
        else:
            self.msg = f"Task '{taskname}' caused an error"
            self.msg += f' (file {filename}).' if filename else '.'
        self.filename=filename
        super().__init__(self.msg)
    
class ExternalTaskError(TaskError):
    """Exception caused due to extranal program to raise in custrom scripts."""
    
    def __init__(self, taskname, custom_message=None, filename='', caller=''):
        self.taskname = taskname
        if custom_message:
            self.msg = custom_message
        else:
            all_args=locals()
            extra_info = ["{}='{}'".format(x, all_args[x]) for x in ['filename', 'caller'] if all_args[x] ]
            self.msg = f"Task '{taskname}' finished with error"
            self.msg += ' ({}).'.format(', '.join(extra_info)) if extra_info else '.'
        self.filename=filename
        self.caller=caller
        super().__init__(taskname, self.msg, filename)
    
