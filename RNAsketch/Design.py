#!/usr/bin/env python
'''
    Design.py: Class as wrapper for ViennaRNA and Nupack
    functions to design an RNA molecule
    This implements the core class which holds all the states of a riboswitch
'''

__author__ = "Stefan Hammer"
__copyright__ = "Copyright 2016"
__version__ = "0.1"
__maintainer__ = "Stefan Hammer"
__email__ = "s.hammer@univie.ac.at"


import re
from State import *

class Design(object):
    '''
    Design contains all neccessary information to generate a RNA device
    or to return a solution. It is used as a container between the different
    functions.

    :param structures: RNA secondary structure string in dot-bracket notation
    :param sequence: RNA sequence string in IUPAC notation [AUGC]
    '''
    def __init__(self, structures, sequence=''):
        self._number_of_structures = None
        self.state = {}

        if isinstance(structures, list):
            for key , struct in enumerate(structures):
                self._parseStructures(key, struct)
        elif isinstance(structures, dict):
            for key, struct in structures.items():
                self._parseStructures(key, struct)
        else:
            raise TypeError('Structures must be a list or a dict hoding the state name and the structure')

        self.sequence = sequence

    @property
    def classtype(self):
        return None

    def _parseStructures(self, key, struct):
        '''
        Function to create a new state given the state-name and the structure in dot-bracket notation

        :param key: Name of the state
        :param struct: Dot-bracket notation of a structure input
        '''
        create_bp_table(struct) #check for balanced brackets
        if not (isinstance(struct, basestring) and re.match(re.compile("[\(\)\.\+\&]"), struct)):
            raise TypeError('Structure must be a string in dot-bracket notation')
        self.newState(str(key), struct)

    def newState(self, key, struct, temperature=37.0, ligand=None, constraint=None, enforce_constraint=False):
        '''
        Creates a new state of the given subclass.

        :param key: Name of the state (string)
        :param struct: Dot-bracket notation of a structure input
        :param temperature: Temperature for the folding predictions of this state (default: 37.0 degree celsius)
        :param ligand: List specifying the ligand binding-pocket and energy, e.g. for Theophylline ["GAUACCAG&CCCUUGGCAGC","(...((((&)...)))...)",-9.22]
        :param constraint: specify a hard constraint string
        :param enforce_constraint: boolean if we should enforce constraints
        '''
        raise NotImplementedError

    @property
    def structures(self):
        '''
        :return: List containing the structures of all states
        '''
        result = []
        for s in self.state:
            if self.state[s].structure not in result:
                result.append(self.state[s].structure)
        return result

    @property
    def sequence(self):
        '''
        :return: Sequence of this design object
        '''
        return self._sequence
    @sequence.setter
    def sequence(self, s):
        if isinstance(s, basestring) and re.match(re.compile("[AUGC\+\&]"), s):
            self._sequence = s
            for state in self.state.values():
                state.reset()
        elif s == '':
            self._sequence = None
        else:
            raise TypeError('Sequence must be a string containing a IUPAC RNA sequence')

    @property
    def number_of_structures(self):
        '''
        :return: Number of uniq structures of all states
        '''
        if not self._number_of_structures:
            self._number_of_structures = len(self.structures)
        return self._number_of_structures

    def write_out(self, score=0):
        '''
        Generates a nice human readable version of all values of this design
        
        :param score: optimization score for this design
        :return: string containing a nicely formatted version of all design values
        '''
        result = '{0:}\t {1:5.2f}'.format(self.sequence, score)
        for k in self.state:
            state = self.state[k]
            result += '\n{0:}'.format(k)
            result += '\n{0:}\t{1:9.4f}\t{2:+9.4f}\t{3:9.4f}'.format(state.structure, state.eos, state.eos-state.mfe_energy, state.pos)
            result += '\n{0:}\t{1:9.4f}'.format(state.mfe_structure, state.mfe_energy)
            result += '\n{0:}\t{1:9.4f}'.format(state.pf_structure, state.pf_energy)
        return result

    def write_csv(self, separator=';'):
        '''
        Generates a csv version of all values of this design separated by the given separator

        :param separator: separator for the values
        :return: string containing all values of this design separated by the given separator
        '''
        result = separator.join(map(str, ['\"' + self.sequence + '\"', self.length, self.number_of_structures ]))
        for state in self.state.values():
            result = separator.join(map(str, [result,
            state.mfe_energy,
            state.mfe_structure,
            state.pf_energy,
            state.pf_structure,
            state.eos,
            state.eos_diff_mfe,
            state.eos_reached_mfe,
            state.pos]))
        return result

    def write_csv_header(self, separator=';'):
        '''
        Generates a csv header for all values of this design separated by the given separator

        :param separator: separator for the values
        :return: string containing a csv header for this design separated by the given separator
        '''
        result = separator.join(['sequence', 'seq_length', 'number_of_structures'])
        strings = ['mfe_energy_', 'mfe_structure_', 'pf_energy_', 'pf_structure_', 'eos_', 'diff_eos_mfe_', 'mfe_reached_', 'prob_']
        for state in self.state:
            for s in strings:
                result += separator + s + state
        return result

    @property
    def eos(self):
        '''
        :return: Dict of energy of structure values of all states with state names as keys
        '''
        result = {}
        for s in self.state:
            result[s] = self.state[s].eos
        return result

    @property
    def pos(self):
        '''
        :return: Dict of probability of structure values of all states with state names as keys
        '''
        result = {}
        for s in self.state:
            result[s] = self.state[s].pos
        return result

    @property
    def eos_diff_mfe(self):
        '''
        :return: Dict of energy of structure to MFE difference values of all states with state names as keys
        '''
        result = {}
        for s in self.state:
            result[s] = self.state[s].eos_diff_mfe
        return result

    @property
    def eos_reached_mfe(self):
        '''
        :return: Dict of booleans telling if the energy of struct equals the mfe energy of all states with state names as keys
        '''
        result = {}
        for s in self.state:
            result[s] = self.state[s].eos_reached_mfe
        return result

    @property
    def mfe_structure(self):
        '''
        :return: Dict of mfe structures of all states with state names as keys
        '''
        result = {}
        for s in self.state:
            result[s] = self.state[s].mfe_structure
        return result

    @property
    def mfe_energy(self):
        '''
        :return: Dict of mfe values of all states with state names as keys
        '''
        result = {}
        for s in self.state:
            result[s] = self.state[s].mfe_energy
        return result
    @property
    def pf_structure(self):
        '''
        :return: Dict of partition function consensus structures of all states with state names as keys
        '''
        result = {}
        for s in self.state:
            result[s] = self.state[s].pf_structure
        return result
    @property
    def pf_energy(self):
        '''
        :return: Dict of partition function energy values of all states with state names as keys
        '''
        result = {}
        for s in self.state:
            result[s] = self.state[s].pf_energy
        return result

    @property
    def ensemble_defect(self):
        '''
        :return: Dict of ensemble defect values of all states with state names as keys
        '''
        result = {}
        for s in self.state:
            result[s] = self.state[s].ensemble_defect
        return result

    @property
    def length(self):
        '''
        :return: Length of the designed sequence
        '''
        return len(self.sequence)

class vrnaDesign(Design):
    @property
    def classtype(self):
        return 'vrna'

    def newState(self, key, struct, temperature=37.0, ligand=None, constraint=None, enforce_constraint=False):
        self.state[key] = vrnaState(self, structure=struct, temperature=temperature, ligand=ligand, constraint=constraint, enforce_constraint=enforce_constraint)

class nupackDesign(Design):
    @property
    def classtype(self):
        return 'nupack'

    def newState(self, key, struct, temperature=37.0, ligand=None, constraint=None, enforce_constraint=False):
        self.state[key] = nupackState(self, structure=struct, temperature=temperature, ligand=ligand, constraint=constraint, enforce_constraint=enforce_constraint)

class pkissDesign(Design):
    @property
    def classtype(self):
        return 'pkiss'

    def newState(self, key, struct, temperature=37.0, ligand=None, constraint=None, enforce_constraint=False):
        self.state[key] = pkissState(self, structure=struct, temperature=temperature, ligand=ligand, constraint=constraint, enforce_constraint=enforce_constraint)

class hotknotsDesign(Design):
    @property
    def classtype(self):
        return 'hotknots'

    def newState(self, key, struct, temperature=37.0, ligand=None, constraint=None, enforce_constraint=False):
        self.state[key] = hotknotsState(self, structure=struct, temperature=temperature, ligand=ligand, constraint=constraint, enforce_constraint=enforce_constraint)

def get_Design(structures, sequence, package, temperature=None):
    '''
    Convenience function to build and return the right Design object

    :param structures: RNA secondary structure string in dot-brackete notation
    :param sequence: RNA sequence string in IUPAC notation [AUGC]
    :param package: String specifying the folding energy evaluation package ('nupack', 'vrna', 'pkiss', 'hotknots')
    :param temperature: Temperature for the folding predictions in degree celsius (default: 37.0)
    '''
    if (package == 'nupack'):
        design = nupackDesign(structures, sequence)
    elif (package == 'vrna'):
        design = vrnaDesign(structures, sequence)
    elif (package == 'pkiss'):
            design = pkissDesign(structures, sequence)
    elif (package == 'hotknots'):
            design = hotknotsDesign(structures, sequence)
    else:
        raise(ValueError('Package parameter set wrongly: ' + package))

    # Set the given temperature for all states
    if temperature:
        for state in design.state.values():
            state.temperature = temperature
    return design
