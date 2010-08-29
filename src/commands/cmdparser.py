"""
The default command parser. Use your own by assigning
settings.ALTERNATE_PARSER to a Python path to a module containing the
replacing cmdparser function. The replacement parser must
return a CommandCandidates object.
"""
import re
from django.conf import settings

# This defines how many space-separated words may at most be in a command.
COMMAND_MAXLEN = settings.COMMAND_MAXLEN

# These chars (and space) end a command name and may
# thus never be part of a command name. Exception is
# if the char is the very first character - the char
# is then treated as the name of the command. 
SPECIAL_CHARS = ["/", "\\", "'", '"', ":", ";", "\-", '#', '=', '!']

# Pre-compiling the regular expression is more effective
REGEX = re.compile(r"""["%s"]""" % ("".join(SPECIAL_CHARS)))

class CommandCandidate(object):
    """
    This is a convenient container for one possible
    combination of command names that may appear if we allow
    many-word commands.     
    """
    def __init__(self, cmdname, args=0, priority=0, obj_key=None):
        "initiate"
        self.cmdname = cmdname
        self.args = args
        self.priority = priority
        self.obj_key = obj_key
    def __str__(self):
        return "<cmdname:'%s',args:'%s'>" % (self.cmdname, self.args)
        
#
# The command parser 
#
def cmdparser(raw_string):
    """
    This function parses the raw string into three parts: command
    name(s), keywords(if any) and arguments(if any). It returns a
    CommandCandidates object.  It should be general enough for most
    game implementations, but you can also overwrite it should you
    wish to implement some completely different way of handling and
    ranking commands. Arguments and keywords are parsed/dealt with by
    each individual command's parse() command.

    The cmdparser understand the following command combinations (where
    [] marks optional parts and <char> is one of the SPECIAL_CHARs
    defined globally.):

    [<char>]cmdname[ cmdname2 cmdname3 ...][<char>] [the rest]

    A command may contain spaces, but never any of of the <char>s. A
    command can maximum have CMD_MAXLEN words, or the number of words
    up to the first <char>, whichever is smallest. An exception is if
    <char> is the very first character in the string - the <char> is
    then assumed to be the actual command name (a common use for this
    is for e.g ':' to be a shortcut for 'emote').
    All words not part of the command name is considered a part of the
    command's argument. Note that <char>s ending a command are never
    removed but are included as the first character in the
    argument. This makes it easier for individual commands to identify
    things like switches. Example: '@create/drop ball' finds the
    command name to trivially be '@create' since '/' ends it. As the
    command's arguments are sent '/drop ball'. In this MUX-inspired
    example, '/' denotes a keyword (or switch) and it is now easy for
    the receiving command to parse /drop as a keyword just by looking
    at the first character.
    
    Allowing multiple command names means we have to take care of all
    possible meanings and the result will be a CommandCandidates
    object with up to COMMAND_MAXLEN names stored in it. So if
    COMMAND_MAXLEN was, say, 4, we would have to search all commands
    matching one of 'hit', 'hit orc', 'hit orc with' and 'hit orc with
    sword' - each which are potentially valid commands. Assuming a
    longer written name means being more specific, a longer command
    name takes precedence over a short one.

    There is one optional form:
    <objname>'s [<char>]cmdname[ cmdname2 cmdname3 ...][<char>] [the rest]

    This is to be used for object command sets with the 'duplicate' flag
    set. It allows the player to define a particular object by name.
    This object name(without the 's) will be stored as obj_key in the
    CommandCandidates object and one version of the command name will be added
    that lack this first part. If a command exists that has the same
    name (including the 's), that command will be used
    instead. Observe that the player setting <objname> will not override
    normal commandset priorities - it's only used if there is no other
    way to differentiate between commands (e.g. two objects in the
    room both having the exact same command names and priorities).
    """    

    def produce_candidates(nr_candidates, wordlist):    
        "Helper function"
        candidates = []
        cmdwords_list = []
        #print "wordlist:",wordlist
        for n_words in range(nr_candidates):                        
            cmdwords_list.append(wordlist.pop(0))
            cmdwords = " ".join([word.strip().lower()
                                 for word in cmdwords_list])            
            args = ""
            for word in wordlist:
                if not args or (word and (REGEX.search(word[0]))):
                    #print "nospace: %s '%s'" % (args, word)
                    args += word                    
                else:
                    #print "space: %s '%s'" % (args, word)
                    args += " %s" % word            
            #print "'%s' | '%s'" % (cmdwords, args)
            candidates.append(CommandCandidate(cmdwords, args, priority=n_words))
        return candidates

    raw_string = raw_string.strip()
    #TODO: check for non-standard characters.
    
    candidates = []
    
    regex_result = REGEX.search(raw_string)
    if not regex_result == None:
        # there are characters from SPECIAL_CHARS in the string.
        # since they cannot be part of a longer command, these
        # will cut short the command, no matter how long we 
        # allow commands to be.
        end_index = regex_result.start()
        end_char = raw_string[end_index]
        if end_index == 0:
            # There is one exception: if the input begins with
            # a special char, we let that be the command name.
            cmdwords = end_char
            if len(raw_string) > 1:
                args = raw_string[1:]
            else:
                args = ""
            candidates.append(CommandCandidate(cmdwords, args))
            return candidates 
        else:
            # the special char occurred somewhere inside the string
            if end_char == "'" and \
                   len(raw_string) > end_index+1 and \
                   raw_string[end_index+1:end_index+3] == "s ":
                # The command is of the form "<word>'s ". The 
                # player might have made an attempt at identifying the 
                # object of which's cmdtable we should prefer (e.g.
                # > red door's button). 
                obj_key = raw_string[:end_index]
                alt_string = raw_string[end_index+2:]                
                alt_candidates = cmdparser(alt_string)
                for candidate in alt_candidates:
                    candidate.obj_key = obj_key
                candidates.extend(alt_candidates)
                # now we let the parser continue as normal, in case
                # the 's -business was not meant to be an obj ref at all.

            # We only run the command finder up until the end char
            nr_candidates = len(raw_string[:end_index].split(None))
            if nr_candidates <= COMMAND_MAXLEN:
                wordlist = raw_string[:end_index].split(" ")                
                wordlist.extend(raw_string[end_index:].split(" "))
                #print "%i, wordlist: %s" % (nr_candidates, wordlist) 
                candidates.extend(produce_candidates(nr_candidates, wordlist))
                return candidates

    # if there were no special characters, or that character
    # was not found within the allowed number of words, we run normally
    nr_candidates = min(COMMAND_MAXLEN,
                        len(raw_string.split(None)))                
    wordlist = raw_string.split(" ")           
    candidates.extend(produce_candidates(nr_candidates, wordlist))
    return candidates
