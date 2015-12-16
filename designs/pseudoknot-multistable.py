from __future__ import print_function

import RNAdesign as rd
import RNA
import argparse
import sys
import re
import math
import signal
import time

# a tri-stable example target. (optional comment)
# ((((....))))....((((....))))........
# ........((((....((((....))))....))))
# ((((((((....))))((((....))))....))))
# below follows a simple (and optional) sequence constraint.
# CKNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNB
# objective function: eos(1)+eos(2)+eos(3) - 3 * gibbs + 1 * ((eos(1)-eos(2))^2 + (eos(1)-eos(3))^2 + (eos(2)-eos(3))^2)

kT = ((37+273.15)*1.98717)/1000.0; # kT = (betaScale*((temperature+K0)*GASCONST))/1000.0; /* in Kcal */

class timeout:
    def __init__(self, seconds=10, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message
    def handle_timeout(self, signum, frame):
        raise Exception(self.error_message)
    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)
    def __exit__(self, type, value, traceback):
        signal.alarm(0)

class Result:
    def __init__(self, sequence, score, structures, number_of_mutations):
        self.sequence = sequence
        self.score = score
        self.structures = structures
        self.number_of_mutations = number_of_mutations
        self.eos = []
        self.probs = []
        
        (self.mfe_struct, self.mfe_energy) = RNA.fold(self.sequence)
        self.part_funct = RNA.pf_fold(self.sequence)[1]
        for struct in self.structures:
            this_eos = RNA.energy_of_struct(self.sequence, struct)
            self.eos.append(this_eos)
            self.probs.append( math.exp((self.part_funct-this_eos) / kT ) )
    def write_out(self):
        #first clean up last line
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()
        print(self.sequence + '\t{0:9.4f}'.format(self.score))
        for i, struct in enumerate(self.structures):
            print(struct + '\t{0:9.4f}\t{1:+9.4f}\t{2:9.4f}'.format(self.eos[i], self.eos[i]-self.mfe_energy, self.probs[i]))
        print(self.mfe_struct + '\t{0:9.4f}'.format(self.mfe_energy))

def main():
    parser = argparse.ArgumentParser(description='Design a tri-stable example same to Hoehner 2013 paper.')
    parser.add_argument("-f", "--file", type = str, default=None, help='Read file in *.inp format')
    parser.add_argument("-i", "--input", default=False, action='store_true', help='Read custom structures and sequence constraints from stdin')
    parser.add_argument("-n", "--number", type=int, default=4, help='Number of designs to generate')
    parser.add_argument("-j", "--jump", type=int, default=1000, help='Do random jumps in the solution space for the first (jump) trials.')
    parser.add_argument("-e", "--exit", type=int, default=1000, help='Exit optimization run if no better solution is aquired after (exit) trials.')
    parser.add_argument("-m", "--mode", type=str, default='sample_global', help='Mode for getting a new sequence: sample, sample_local, sample_global')
    parser.add_argument("-k", "--kill", type=int, default=120, help='Timeout value of graph construction in seconds. (default: 120)')
    parser.add_argument("-g", "--graphml", type=str, default=None, help='Write a graphml file with the given filename.')
    parser.add_argument("-c", "--csv", default=False, action='store_true', help='Write output as semi-colon csv file to stdout')
    parser.add_argument("-p", "--progress", default=False, action='store_true', help='Show progress of optimization')
    parser.add_argument("-d", "--debug", default=False, action='store_true', help='Show debug information of library')
    args = parser.parse_args()

    print("# Options: number={0:d}, jump={1:d}, exit={2:d}, mode={3:}".format(args.number, args.jump, args.exit, args.mode))
    rd.initialize_library(args.debug)
    # define structures
    structures = []
    constraint = ""
    if (args.input):
        for line in sys.stdin:
            if re.match(re.compile("[\(\)\.]"), line, flags=0): # TODO add brackets <{([
                structures.append(line.rstrip('\n'))
            elif re.match(re.compile("[ACGTUWSMKRYBDHVN]"), line, flags=0):
                constraint = line.rstrip('\n')
            elif re.search(re.compile("@"), line, flags=0):
                break;
    elif (args.file is not None):
        print("# Input File: {0:}".format(args.file))
        with open(args.file) as f:
            data = f.read()
            lines = data.split("\n")
            for line in lines:
                if re.match(re.compile("[\(\)\.]"), line): # TODO add brackets <{([
                    structures.append(line)
                if re.match(re.compile("[\ AUGC]"), line):
                    elements = str(line)
                    constraint = elements.replace(" ", "N")
                if line.startswith(";"):
                    break
    else:
        structures = ['((((....))))....((((....))))........',
            '........((((....((((....))))....))))',
            '((((((((....))))((((....))))....))))']
        constraint = 'NNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN'
    
    # try to construct dependency graph, catch errors and timeouts
    dg = None
    graph_construction = 0
    construction_time = 0.0
    sample_time = 0.0
    max_specials = 0
    max_component_vertices = 0
    max_special_ratio = 0
    mean_special_ratio = 0
    num_cc = 0
    nos = 0
    
    
    # construct dependency graph with these structures
    try:
        with timeout(seconds=args.kill):
            start = time.clock()
            dg = rd.DependencyGraphMT(structures)
            construction_time = time.clock() - start
    except Exception as e:
        print( "Error: %s" % e , file=sys.stderr)

    if (dg is not None):
        # general DG values
        print("# " + "\n# ".join(structures) + "\n# " + constraint)
        # print the amount of solutions
        print('# Maximal number of solutions: ' + str(dg.number_of_sequences()))
        # print the amount of connected components
        number_of_components = dg.number_of_connected_components()
        print('# Number of Connected Components: ' + str(number_of_components))
        for i in range(0, number_of_components):
            print('# [' + str(i) + ']' + str(dg.component_vertices(i)))
        
        # remember general DG values
        graph_construction = 1
        num_cc = dg.number_of_connected_components()
        nos = dg.number_of_sequences()
        special_ratios = []
        for cc in range(0, num_cc):
            cv = len(dg.component_vertices(cc))
            sv = len(dg.special_vertices(cc))
            special_ratios.append(float(sv)/float(cv))
            if (max_specials < sv):
                max_specials = sv
            if (max_component_vertices < cv):
                max_component_vertices = cv
        max_special_ratio = max(special_ratios)
        mean_special_ratio = sum(special_ratios)/len(special_ratios)

        # if requested write out a graphml file
        if args.graphml is not None:
            with open(args.graphml, 'w') as f:
                f.write(dg.get_graphml() + "\n")

        # print header for csv file
        if (args.csv):
            mfe_reached_str = ""
            diff_eos_mfe_str = ""
            for s in range(0, len(structures)):
                mfe_reached_str = mfe_reached_str + "mfe_reached_" + str(s) +";"
                diff_eos_mfe_str = diff_eos_mfe_str + "diff_eos_mfe_" + str(s) + ";"
            print(";".join(["jump",
                        "exit",
                        "mode",
                        "num_mutations", 
                        "seq_length",
                        "sequence",
                        "graph_construction",
                        "num_cc",
                        "max_specials",
                        "max_component_vertices",
                        "max_special_ratio",
                        "mean_special_ratio",
                        "nos",
                        "construction_time",
                        "sample_time"]) + ";" + 
                        mfe_reached_str + 
                        diff_eos_mfe_str)
        
        # main loop from zero to number of solutions
        for n in range(0, args.number):
            start = time.clock()
            r = optimization_run(dg, structures, args)
            sample_time = time.clock() - start
            if (args.csv):
                # process result and write result of this optimization to stdout
                diff_eos_mfe = []
                mfe_reached = []
                for i in range(0, len(r.structures)):
                    mfe_reached.append(0)
                    eos_mfe = r.eos[i] - r.mfe_energy
                    diff_eos_mfe.append(eos_mfe)
                    if r.eos[i] == r.mfe_energy:
                        mfe_reached[i] = 1

                if (args.progress):
                    sys.stdout.write("\r" + " " * 60 + "\r")
                    sys.stdout.flush()

                print(args.jump,
                        args.exit,
                        "\"" + args.mode + "\"",
                        r.number_of_mutations, 
                        len(r.sequence),
                        "\"" + r.sequence + "\"",
                        graph_construction,
                        num_cc,
                        max_specials,
                        max_component_vertices,
                        max_special_ratio,
                        mean_special_ratio,
                        nos,
                        construction_time,
                        sample_time,
                        *(mfe_reached + diff_eos_mfe), sep=";")
            else:
                r.write_out()

# main optimization
def optimization_run(dg, structures, args):
    score = 0
    count = 0
    jumps = args.jump
    # print this sequence with score
    score = calculate_objective(dg.get_sequence(), structures);
    #print dg.get_sequence() + '\t' + str(score)
    
    # sample globally for num_opt times and print
    i = 0
    while 1:
        # sample sequence
        if jumps:
            mut_nos = dg.sample()
            jumps -= 1
            count = 0
        else:
            if args.mode == 'sample':
                mut_nos = dg.sample()
            elif args.mode == 'sample_global':
                mut_nos = dg.sample_global()
            elif args.mode == 'sample_local':
                mut_nos = dg.sample_local()
            else:
                sys.stdout.write("Wrong sample argument: " + args.mode + "\n")
                sys.exit(1)
        # write progress
        if (args.progress):
            sys.stdout.write("\rMutate: {0:7.0f}/{1:5.0f} from NOS: {2:7.0f}".format(i, count, mut_nos) + " " * 20)
            sys.stdout.flush()
        
        this_score = calculate_objective(dg.get_sequence(), structures);
        
        if (this_score < score):
            score = this_score
            count = 0
        else:
            dg.revert_sequence();
            count += 1
            if count > args.exit:
                break
        i += 1
    
    # finally return the result
    return Result(dg.get_sequence(), score, structures, i)

# objective function: eos(1)+eos(2)+eos(3) - 3 * gibbs + 1 * ((eos(1)-eos(2))^2 + (eos(1)-eos(3))^2 + (eos(2)-eos(3))^2)
def calculate_objective(sequence, structures):
    eos = []
    for struct in structures:
        eos.append(RNA.energy_of_struct(sequence, struct)) # TODO change do NUPACK.energy(arguments) ???
    
    gibbs = RNA.pf_fold(sequence) # TODO change to NUPACK.pfunc(arguments)
    
    objective_difference_part = 0
    for i, value in enumerate(eos):
        for j in eos[i+1:]:
            objective_difference_part += math.fabs(value - j)
    
    return sum(eos) - len(eos) * gibbs[1] + 1 * objective_difference_part

if __name__ == "__main__":
    main()

