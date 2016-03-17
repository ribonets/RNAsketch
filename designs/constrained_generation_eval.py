from __future__ import print_function

try:
    from PyDesign import *
    import PyDesign
except ImportError, e:
    print(e.message)
    exit(1)

import RNAdesign as rd
import argparse
import sys
import time

# This script logs everything during the optimization


def main():
    parser = argparse.ArgumentParser(description='Design a tri-stable example same to Hoehner 2013 paper.')
    parser.add_argument("-f", "--file", type = str, default=None, help='Read file in *.inp format')
    parser.add_argument("-i", "--input", default=False, action='store_true', help='Read custom structures and sequence constraints from stdin')
    parser.add_argument("-q", "--nupack", default=False, action='store_true', help='Use Nupack instead of the ViennaRNA package (for pseudoknots)')
    parser.add_argument("-n", "--number", type=int, default=4, help='Number of designs to generate')
    parser.add_argument("-e", "--exit", type=int, default=500, help='Exit optimization run if no better solution is aquired after (exit) trials.')
    parser.add_argument("-m", "--mode", type=str, default='sample_global', help='Mode for getting a new sequence: sample, sample_local, sample_global, sample_strelem')
    parser.add_argument("-x", "--max_eos_diff", type=float, default=0, help='Energy of Struct difference allowed during constrained generation')
    parser.add_argument("-s", "--size_constraint", type=int, default=100, help='Size of negative constraints container')
    parser.add_argument("-k", "--kill", type=int, default=0, help='Timeout value of graph construction in seconds. (default: infinite)')
    parser.add_argument("-g", "--graphml", type=str, default=None, help='Write a graphml file with the given filename.')
    parser.add_argument("-c", "--csv", default=False, action='store_true', help='Write output as semi-colon csv file to stdout')
    parser.add_argument("-p", "--progress", default=False, action='store_true', help='Show progress of optimization')
    parser.add_argument("-d", "--debug", default=False, action='store_true', help='Show debug information of library')
    args = parser.parse_args()
    
    print("# Options: number={0:d}, exit={1:d}, size_constraint={2:d}, mode={3:}, nupack={4:}".format(args.number, args.exit, args.size_constraint, args.mode, str(args.nupack)))
    rd.initialize_library(args.debug, args.kill)
    # define structures
    structures = []
    constraint = ''
    start_sequence = ''
    
    if (args.input):
        data = ''
        for line in sys.stdin:
            data = data + '\n' + line
        (structures, constraint, start_sequence) = read_input(data)
    elif (args.file is not None):
        print("# Input File: {0:}".format(args.file))
        (structures, constraint, start_sequence) = read_inp_file(args.file)
    else:
        structures = ['((((....))))....((((....))))........',
            '........((((....((((....))))....))))',
            '((((((((....))))((((....))))....))))']
        constraint = 'NNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN'
    # try to construct dependency graph, catch errors and timeouts
    dg = None
    # remember values in a dict
    values = { "score":float('inf'), "num_mutations":0, "num_mfes":0, "num_objectives":0, "num_eos":0, "num_samples":0, "construction_time":0, "sample_time":0 }
        
    # construct dependency graph with these structures
    try:
        start = time.clock()
        dg = rd.DependencyGraphMT(structures, constraint)
        values["construction_time"] = time.clock() - start
    except Exception as e:
        print( "Error: %s" % e , file=sys.stderr)
    
    # general DG values
    print("# " + "\n# ".join(structures) + "\n# " + constraint)

    if (dg is not None):
        
        # if requested write out a graphml file
        if args.graphml is not None:
            with open(args.graphml, 'w') as f:
                f.write(dg.get_graphml() + "\n")
        
        # print the amount of solutions
        print('# Maximal number of solutions: ' + str(dg.number_of_sequences()))
        # print the amount of connected components
        number_of_components = dg.number_of_connected_components()
        print('# Number of Connected Components: ' + str(number_of_components))
        for i in range(0, number_of_components):
            print('# [' + str(i) + ']' + str(dg.component_vertices(i)))
        
        # remember general DG values
        graph_properties = get_graph_properties(dg)
        
        # create a initial design object
        if (args.nupack):
            design = nupackDesign(structures, start_sequence)
        else:
            design = vrnaDesign(structures, start_sequence)
        
        # print header for csv file
        if (args.csv):
            print(";".join(["exit",
                        "mode",
                        "time",
                        design.write_csv_header()] +
                        values.keys() + 
                        graph_properties.keys()))
        
        # main loop from zero to number of solutions
        for n in range(0, args.number):
            # reset the design object
            if (args.nupack):
                design = nupackDesign(structures, start_sequence)
            else:
                design = vrnaDesign(structures, start_sequence)
            
            # now do the optimization based on the chose mode
            try:
                constraint_generation_optimization_eval(args, graph_properties,
                            dg, design, exit=args.exit, mode=args.mode, 
                            num_neg_constraints=args.size_constraint, max_eos_diff=args.max_eos_diff, progress=args.progress)
            except ValueError as e:
                print (e.value)
                exit(1)
    else:
        print('# Construction time out reached!')

def logging_breakpoint(optimization_start, minutes, values, design, graph_properties, args):
    timestamp = 10 * minutes
    if (time.clock() - optimization_start > timestamp):
        if (args.progress):
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()
        values["sample_time"] = time.clock() - optimization_start
        if (args.csv):
            print(args.exit,
                    "\"" + args.mode + "\"",
                    timestamp,
                    design.write_csv(),
                    *(values.values() + 
                    graph_properties.values()), sep=";")
        else:
            print(design.write_out(score))
        return minutes + 1
    else:
        return minutes

def constraint_generation_optimization_eval(args, graph_properties, dg, design, objective_function=calculate_objective, exit=1000, mode='sample', num_neg_constraints=100, max_eos_diff=0, progress=False):
    '''
    Takes a Design object and does a constraint generation optimization of this sequence.
    :param dg: RNAdesign DependencyGraph object
    :param design: Design object containing the sequence and structures
    :param objective_functions: array of functions which takes a design object and returns a score for evaluation
    :param exit: Number of unsuccessful new sequences before exiting the optimization
    :param mode: String defining the sampling mode: sample, sample_global, sample_local
    :param num_neg_constraints: Maximal number of negative constraints to accumulate during the optimization process
    :param max_eos_diff: Maximal difference between eos of the negative and positive constraints
    :param progress: Whether or not to print the progress to the console
    :param return: Optimization score reached for the final sequence
    "param return: Number of samples neccessary to reach this result
    '''
    dg.set_history_size(100)
    neg_constraints = collections.deque(maxlen=num_neg_constraints)

    # if the design has no sequence yet, sample one from scratch
    if not design.sequence:
        dg.sample()
        design.sequence = dg.get_sequence()
    else:
        dg.set_sequence(design.sequence)
    
    score = objective_function(design)
    # count for exit condition
    count = 0
    # remember how many mutations were done
    number_of_samples = 0
    # remember evalutaion values
    # remember total time
    optimization_start = time.clock()
    minutes = 0
    values = { "score":score, "num_mutations":0, "num_mfes":0, "num_objectives":1, "num_eos":0, "num_samples":0, "construction_time":0, "sample_time":0 }
    
    # main optimization loop
    while True:
        minutes = logging_breakpoint(optimization_start, minutes, values, design, graph_properties, args)
        # constraint generation loop
        while True:
            minutes = logging_breakpoint(optimization_start, minutes, values, design, graph_properties, args)
            # count up the mutations
            number_of_samples += 1
            values["num_samples"] += 1
            
            # sample a new sequence
            (mut_nos, sample_count) = PyDesign._sample_sequence(dg, design, mode)
            
            # write progress
            if progress:
                sys.stdout.write("\rMutate: {0:7.0f}/{1:5.0f} | EOS-Diff: {2:4.2f} | Scores: {3:5.2f} | NOS: {4:.5e}".format(number_of_samples, count, max_eos_diff, score, mut_nos))
                sys.stdout.flush()
            # boolean if it is perfect already
            perfect = True
            values["num_eos"] += design.number_of_structures
            # evaluate the constraints
            for negc in reversed(neg_constraints):
                minutes = logging_breakpoint(optimization_start, minutes, values, design, graph_properties, args)
                # test if the newly sampled sequence is compatible to the neg constraint, if not -> Perfect!
                if rd.sequence_structure_compatible(design.sequence, [negc]):
                    # count up number eos
                    values["num_eos"] += 1
                    if design.classtype == 'vrnaDesign':
                        neg_eos = RNA.energy_of_struct(design.sequence, negc)
                    elif design.classtype == 'nupackDesign':
                        neg_eos = nupack.energy([design.sequence], negc, material = 'rna', pseudo = True)
                    else:
                        raise ValueError('Could not figure out the classtype of the Design object.')
                    # test if the newly sampled sequence emfe_struos for pos constraints is lower than
                    # the eos for all negative constraints, if not -> Perfect!
                    for k in range(0, design.number_of_structures):
                        if float(neg_eos) - float(design.eos[k]) < max_eos_diff:
                            # this is no better solution, revert!
                            perfect = False
                            dg.revert_sequence(sample_count)
                            design.sequence = dg.get_sequence()
                            break
                # if this is no perfect solution, stop evaluating and sample a new one
                if not perfect:
                    break
            # if solution is perfect, stop the optimization and go down to score calculation
            if perfect:
                break
        
        # count this as a solution to analyse
        count += 1
        this_score = objective_function(design)
        values["num_objectives"] += 1
        minutes = logging_breakpoint(optimization_start, minutes, values, design, graph_properties, args)
        if (this_score < score):
            score = this_score
            values["score"] = score
            # reset values
            count = 0
        else:
            dg.revert_sequence(sample_count)
            design.sequence = dg.get_sequence()
        # else if current mfe is not in negative constraints, add to it
        # count calculated mfes 
        values["num_mfes"] += 1
        for mfe_str in design.mfe_structure:
            if mfe_str not in design.structures:
                if mfe_str not in neg_constraints:
                    neg_constraints.append(mfe_str)
                    #print('\n'+'\n'.join(neg_constraints))
        minutes = logging_breakpoint(optimization_start, minutes, values, design, graph_properties, args)
        # exit condition
        if count > exit:
            break
        
    # clear the console
    if (progress):
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()
    # finally return the result
    return values

if __name__ == "__main__":
    main()


