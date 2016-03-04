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



def main():
    parser = argparse.ArgumentParser(description='Design a tri-stable example same to Hoehner 2013 paper.')
    parser.add_argument("-f", "--file", type = str, default=None, help='Read file in *.inp format')
    parser.add_argument("-i", "--input", default=False, action='store_true', help='Read custom structures and sequence constraints from stdin')
    parser.add_argument("-q", "--nupack", default=False, action='store_true', help='Use Nupack instead of the ViennaRNA package (for pseudoknots)')
    parser.add_argument("-n", "--number", type=int, default=4, help='Number of designs to generate')
    parser.add_argument("-j", "--jump", type=int, default=300, help='Do random jumps in the solution space for the first (jump) trials.')
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
    
    print("# Options: number={0:d}, jump={1:d}, exit={2:d}, size_constraint={3:d}, mode={4:}, nupack={5:}".format(args.number, args.jump, args.exit, args.size_constraint, args.mode, str(args.nupack)))
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
    construction_time = 0.0
    sample_time = 0.0
        
    # construct dependency graph with these structures
    try:
        start = time.clock()
        dg = rd.DependencyGraphMT(structures, constraint)
        construction_time = time.clock() - start
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
            print(";".join(["jump",
                        "exit",
                        "mode",
                        "score",
                        "num_mutations",
                        "construction_time",
                        "sample_time",
                        "num_samples",
                        "num_mfes",
			"num_eos",
			"num_objectives",
                        design.write_csv_header()] +
                        graph_properties.keys()))

        # main loop from zero to number of solutions
        for n in range(0, args.number):
            # reset the design object
            if (args.nupack):
                design = nupackDesign(structures, start_sequence)
            else:
                design = vrnaDesign(structures, start_sequence)
            
            start = time.clock()
            # do a complete sampling jump times
            (scores, number_of_jumps) = classic_optimization(dg, design, exit=args.jump, mode='sample', progress=args.progress)
            # now do the optimization based on the chose mode
            try:
                (scores, number_of_mutations,number_mfes, number_objectives, number_eos, number_samples) = constraint_generation_optimization_eval(dg, design, exit=args.exit, mode=args.mode, 
                            num_neg_constraints=args.size_constraint, max_eos_diff=args.max_eos_diff, progress=args.progress)
            except ValueError as e:
                print (e.value)
                exit(1)
            # sum up for a complete number of mutations
            number_of_mutations += number_of_jumps
            sample_time = time.clock() - start
            
            if (args.csv):
                print(args.jump,
                        args.exit,
                        "\"" + args.mode + "\"",
                        scores[0],
                        number_of_mutations,
                        construction_time,
                        sample_time,
                        number_samples,
                        number_mfes,
                        number_eos,
                        number_objectives,
                        design.write_csv(),
                        *graph_properties.values(), sep=";")
            else:
                print(design.write_out(scores))
    else:
        print('# Construction time out reached!')

def constraint_generation_optimization_eval(dg, design, objective_functions=[calculate_objective], exit=1000, mode='sample', num_neg_constraints=100, max_eos_diff=0, progress=False):
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
    
    neg_constraints = collections.deque(maxlen=num_neg_constraints)
    
    # count calculated objectives
    number_objectives = 0

    # if the design has no sequence yet, sample one from scratch
    if not design.sequence:
        dg.sample()
        design.sequence = dg.get_sequence()
    else:
        dg.set_sequence(design.sequence)
    
    scores = []
    for obj_fun in objective_functions:
        scores.append(obj_fun(design))
        number_objectives += 1
    # count for exit condition
    count = 0
    # remember how many mutations were done
    number_of_samples = 0
    number_samples = 0
    # count mfes
    number_mfes = 0
    # count eos
    number_eos = 0
    # sample steps to do
    sample_steps = 1
    # count for unsucessful constraint generation sequences
    cg_count = 0
    
    # main optimization loop
    while True:
        # constraint generation loop
        while True:
            # count up the mutations
            number_of_samples += 1
            number_samples += 1
            # evaluate cg_count and make search space bigger if necessary
            if (cg_count > 10000):
                cg_count = 0
                sample_steps += 1
                dg.set_history_size(sample_steps+100)
            # increase cg_count
            cg_count += 1
            
            # sample a new sequence
            (mut_nos, sample_count) = PyDesign._sample_sequence(dg, design, mode, sample_steps)
            
            # write progress
            if progress:
                formatted_scores = "; ".join(["%5.2f" % score for score in scores])
                sys.stdout.write("\rMutate: {0:7.0f}/{1:5.0f} | Steps: {2:3d} | EOS-Diff: {3:4.2f} | Scores: {4:} | NOS: {5:.5e}".format(number_of_samples, count, sample_steps, max_eos_diff, formatted_scores, mut_nos) + " " * 20)
                sys.stdout.flush()
            # boolean if it is perfect already
            perfect = True
            number_eos += design.number_of_structures
            # evaluate the constraints
            for negc in reversed(neg_constraints):
                # test if the newly sampled sequence is compatible to the neg constraint, if not -> Perfect!
                if rd.sequence_structure_compatible(design.sequence, [negc]):
                    # count up number eos
                    number_eos += 1
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
        # count calculated mfes 
        number_mfes += 1
        # if we reached the mfe strcture, calculate a score for this solution and evaluate
        if design.mfe_structure in design.structures:
            # calculate objective
            this_scores = []
            
            for obj_fun in objective_functions:
                this_scores.append(obj_fun(design))
                # count up number of objectives
                number_objectives += 1
            # evaluate
            better = False
            for i, score in enumerate(scores):
                if (this_scores[i] > score):
                    better = False
                    break
                elif (this_scores[i] < score):
                    better = True

            if (better):
                scores = this_scores
                # reset values
                sample_steps = 1
                cg_count = 0
                count = 0
            else:
                dg.revert_sequence(sample_count)
                design.sequence = dg.get_sequence()
        # else if current mfe is not in negative constraints, add to it
        else:
            if design.mfe_structure not in neg_constraints:
                neg_constraints.append(design.mfe_structure)
                #print('\n'+'\n'.join(neg_constraints))

            dg.revert_sequence(sample_count)
            design.sequence = dg.get_sequence()
        
        # exit condition
        if count > exit:
            break
        
    # clear the console
    if (progress):
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()
    # finally return the result
    return scores, number_of_samples, number_mfes, number_objectives, number_eos, number_samples

if __name__ == "__main__":
    main()


