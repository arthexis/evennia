"""
A cmdset holds a set of commands available to the object or to other
objects near it. All the commands a player can give (look, @create etc)
are stored as the default cmdset on the player object and managed using the
CmdHandler object (see cmdhandler.py).

The power of having command sets in CmdSets like this is that CmdSets
can be merged together according to individual rules to create a new
on-the-fly CmdSet that is some combination of the
previous ones. Their function are borrowed to a large parts from mathematical
Set theory, it should not be much of a problem to understand.

See CmdHandler for practical examples on how to apply cmdsets 
together to create interesting in-game effects.
"""

import copy

class CmdSetMeta(type):
    """
    This metaclass makes some minor on-the-fly convenience fixes to
    the cmdset class.
    """
    def __init__(mcs, *args, **kwargs):
        """
        Fixes some things in the cmdclass
        """
        # by default we key the cmdset the same as the
        # name of its class. 
        mcs.key = mcs.__name__

        if not type(mcs.key_mergetypes) == dict:
            mcs.key_mergetypes = {}
        super(CmdSetMeta, mcs).__init__(*args, **kwargs)


# Some priority-sensitive merge operations for cmdsets

def union(cmdset_a, cmdset_b, duplicates=False):
    "C = A U B. CmdSet A is assumed to have higher priority"
    cmdset_c = cmdset_a.copy_this()
    # we make copies, not refs by use of [:]
    cmdset_c.commands = cmdset_a.commands[:] 
    if duplicates and cmdset_a.priority == cmdset_b.priority:
        cmdset_c.commands.extend(cmdset_b.commands)
    else:
        cmdset_c.commands.extend([cmd for cmd in cmdset_b
                               if not cmd in cmdset_a])
    return cmdset_c            

def intersect(cmdset_a, cmdset_b, duplicates=False):
    "C = A (intersect) B. A is assumed higher priority"
    cmdset_c = cmdset_a.copy_this()
    if duplicates and cmdset_a.priority == cmdset_b.priority:
        for cmd in [cmd for cmd in cmdset_a if cmd in cmdset_b]:
            cmdset_c.add(cmd)
            cmdset_c.add(cmdset_b.get(cmd))
    else:
        cmdset_c.commands = [cmd for cmd in cmdset_a if cmd in cmdset_b]
    return cmdset_c                    

def replace(cmdset_a, cmdset_b, cmdset_c):
    "C = A + B where the result is A."
    cmdset_c = cmdset_a.copy_this()
    cmdset_c.commands = cmdset_a.commands[:] 
    return cmdset_c

def remove(cmdset_a, cmdset_b, cmdset_c):
    "C = A + B, where B is filtered by A"
    cmdset_c = cmdset_a.copy_this()
    cmdset_c.commands = [cmd for cmd in cmdset_b if not cmd in cmdset_a]
    return cmdset_c

def instantiate(cmd):
    """
    checks so that object is an instantiated command
    and not, say a cmdclass. If it is, instantiate it.
    Other types, like strings, are passed through. 
    """    
    if callable(cmd):
        # this is a valid check since Command *instances*
        # don't implement __call__, so this will catch 
        # Command *classes* and instantiate them.
        return cmd()
    return cmd 
        
class CmdSet(object):
    """
    This class describes a unique cmdset that understands priorities. CmdSets
    can be merged and made to perform various set operations on each other.
    CmdSets have priorities that affect which of their ingoing commands gets used.
        
        In the examples, cmdset A always have higher priority than cmdset B.       

        key - the name of the cmdset. This can be used on its own for game operations         

        mergetype (partly from Set theory):     

            Union -    The two command sets are merged so that as many
                        commands as possible of each cmdset ends up in the
                        merged cmdset. Same-name commands are merged by
                        priority.  This is the most common default.
                        Ex: A1,A3 + B1,B2,B4,B5 = A1,B2,A3,B4,B5
            Intersect - Only commands found in *both* cmdsets
                        (i.e. which have same names) end up in the merged
                        cmdset, with the higher-priority cmdset replacing the
                        lower one.  Ex: A1,A3 + B1,B2,B4,B5 = A1
            Replace -   The commands of this cmdset completely replaces
                        the lower-priority cmdset's commands, regardless
                        of if same-name commands exist.
                        Ex: A1,A3 + B1,B2,B4,B5 = A1,A3
            Remove -    This removes the relevant commands from the
                        lower-priority cmdset completely.  They are not
                        replaced with anything, so this in effects uses the
                        high-priority cmdset as a filter to affect the
                        low-priority cmdset.
                        Ex: A1,A3 + B1,B2,B4,B5 = B2,B4,B5

                     Note: Commands longer than 2 characters and starting
                           with double underscrores, like '__noinput_command'
                           are considered 'system commands' and are
                           excempt from all merge operations - they are
                           ALWAYS included across mergers and only affected
                           if same-named system commands replace them.
                           
        priority- All cmdsets are always merged in pairs of two so that
                  the higher set's mergetype is applied to the
                  lower-priority cmdset. Evennia uses priorities from 0-10
                  where 10 are used for high-priority things like comsys
                  channel names and 9 for exit names in order to give
                  these priority when the given command matches.
        
        duplicates - determines what happens when two sets of equal
                     priority merge. Default has the first of them in the
                     merger (i.e. A above) automatically taking
                     precedence. But if allow_duplicates is true, the
                     result will be a merger with more than one of each
                     name match.  This will usually lead to the player
                     receiving a multiple-match error higher up the road,
                     but can be good for things like cmdsets on non-player
                     objects in a room, to allow the system to warn that
                     more than one 'ball' in the room has the same 'kick'
                     command defined on it, so it may offer a chance to
                     select which ball to kick ...  Allowing duplicates
                     only makes sense for Union and Intersect, the setting
                     is ignored for the other mergetypes.
    
        key_mergetype (dict) - allows the cmdset to define a unique
                 mergetype for particular cmdsets.  Format is
                 {CmdSetkeystring:mergetype}. Priorities still apply.
                 Example: {'Myevilcmdset','Replace'} which would make
                 sure for this set to always use 'Replace' on
                 Myevilcmdset no matter what overall mergetype this set
                 has.

        no_objs  - don't include any commands from nearby objects 
                      when searching for suitable commands
        no_exits  - ignore the names of exits when matching against
                            commands
        no_channels   - ignore the name of channels when matching against
                            commands (WARNING- this is dangerous since the
                            player can then not even ask staff for help if
                            something goes wrong)           


    """
    __metaclass__ = CmdSetMeta

    key = "Unnamed CmdSet"
    mergetype = "Union"
    priority = 0
    duplicates = False
    key_mergetypes = {}
    no_exits = False
    no_objs = False
    no_channels = False 

    def __init__(self, cmdsetobj=None, key=None):
        """ 
        Creates a new CmdSet instance.

        cmdsetobj - this is the database object to which this particular
             instance of cmdset is related. It is often a player but may also be a 
             regular object.
        """
        if key:
            self.key = key
        self.commands = []
        self.actual_mergetype = self.mergetype
        self.cmdsetobj = cmdsetobj
        # initialize system
        self.at_cmdset_creation()

    def at_cmdset_creation(self):        
        """
        Hook method - this should be overloaded in the inheriting
        class, and should take care of populating the cmdset
        by use of self.add().
        """   
        pass

    def add(self, cmd):
        """
        Add a command to this cmdset.

        Note that if cmd already has 
        """
        cmd = instantiate(cmd)
        if cmd:
            if not hasattr(cmd, 'obj'):
                cmd.obj = self.cmdsetobj
            self.commands.append(cmd)
            self.commands = list(set(self.commands))

    def remove(self, cmd):
        """
        Remove a command instance from the cmdset.
        cmd can be either a cmd instance or a key string. 
        """
        cmd = instantiate(cmd)
        self.commands = [oldcmd for oldcmd in self.commands
                             if oldcmd != cmd]
                                 
    def get(self, cmd):
        """
        Return the command in this cmdset that matches the
        given command. cmd may be either a command instance or
        a key string. 
        """
        cmd = instantiate(cmd)
        if cmd:
            for thiscmd in self.commands:
                if thiscmd == cmd:
                    return thiscmd 

    def get_system_cmds(self):
        """
        Return system commands in the cmdset, defined as
        commands starting with double underscore __.
        These are excempt from merge operations. 
        """
        return [cmd for cmd in self.commands
                if len(cmd.key) > 2 and cmd.key[:2] == '__']

    def copy_this(self):
        """
        Returns a new cmdset with the same settings as this one
        (no commands are copied over)
        """
        cmdset = CmdSet()
        cmdset.key = self.key
        cmdset.cmdsetobj = self.cmdsetobj
        cmdset.no_exits = self.no_exits
        cmdset.no_objs = self.no_objs
        cmdset.no_channels = self.no_channels
        cmdset.mergetype = self.mergetype
        cmdset.priority = self.priority
        cmdset.duplicates = self.duplicates
        cmdset.key_mergetypes = copy.deepcopy(self.key_mergetypes)
        return cmdset
        
    
    def __str__(self):
        """
        Show all commands in cmdset when printing it. 
        """
        return ", ".join([str(cmd) for cmd in self.commands])
        
    def __iter__(self):
        """
        Allows for things like 'for cmd in cmdset':
        """
        return iter(self.commands)

    def __contains__(self, othercmd):
        """
        Returns True if this cmdset contains the given command (as defined
        by command name and aliases). This allows for things like 'if cmd in cmdset'
        """
        return any(cmd == othercmd for cmd in self.commands)
               
    def __add__(self, cmdset_b):
        """
        Merge this cmdset (A) with another cmdset (B) using the + operator,

        C = A + B 

        Here, we (by convention) say that 'A is merged onto B to form
        C'.  The actual merge operation used in the 'addition' depends
        on which priorities A and B have. The one of the two with the
        highest priority will apply and give its properties to C. In
        the case of a tie, A takes priority and replaces the
        same-named commands in B unless A has the 'duplicate' variable
        set (which means both sets' commands are kept).
        """

        # It's okay to merge with None
        if not cmdset_b:
            return self

        # preserve system __commands
        sys_commands = self.get_system_cmds() + cmdset_b.get_system_cmds()

        if self.priority >= cmdset_b.priority: 
            # A higher or equal priority than B
            mergetype = self.key_mergetypes.get(cmdset_b.key,
                                                self.mergetype)            
            if mergetype == "Intersect":
                cmdset_c = intersect(self, cmdset_b, cmdset_b.duplicates)
            elif mergetype == "Replace":
                cmdset_c = replace(self, cmdset_b, cmdset_b.duplicates)
            elif mergetype == "Remove":
                cmdset_c = remove(self, cmdset_b, cmdset_b.duplicates)
            else: # Union
                cmdset_c = union(self, cmdset_b, cmdset_b.duplicates)
        else:
            # B higher priority than A
            mergetype = cmdset_b.key_mergetypes.get(self.key,
                                                 cmdset_b.mergetype)  
            if mergetype == "Intersect":
                cmdset_c = intersect(cmdset_b, self, self.duplicates)
            elif mergetype == "Replace":
                cmdset_c = replace(cmdset_b, self, self.duplicates)
            elif mergetype == "Remove":
                cmdset_c = remove(self, cmdset_b, self.duplicates)
            else: # Union
                cmdset_c = union(cmdset_b, self, self.duplicates)

        # we store actual_mergetype since key_mergetypes
        # might be different from the main mergetype.
        # This is used for diagnosis.
        cmdset_c.actual_mergetype = mergetype 

        # return the system commands to the cmdset
        for cmd in sys_commands:
            cmdset_c.add(cmd)

        return cmdset_c 
