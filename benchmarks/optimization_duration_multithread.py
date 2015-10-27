import RNAdesign as rd
import RNA
import argparse
import sys
import re

# a tri-stable example target. (optional comment)
# ((((....))))....((((....))))........
# ........((((....((((....))))....))))
# ((((((((....))))((((....))))....))))
# below follows a simple (and optional) sequence constraint.
# CKNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNB
# objective function: eos(1)+eos(2)+eos(3) - 3 * gibbs + 1 * ((eos(1)-eos(2))^2 + (eos(1)-eos(3))^2 + (eos(2)-eos(3))^2)

class Result:
    def __init__(self, sequence, score, structures):
        self.sequence = sequence
        self.score = score
        self.structures = structures
        self.eos = []
        
        (self.mfe_struct, self.mfe_energy) = RNA.fold(self.sequence)
        for struct in self.structures:
            self.eos.append(RNA.energy_of_struct(self.sequence, struct))
    def write(self):
        print(self.sequence + '\t{0:4.5f}'.format(self.score))
        for i, struct in enumerate(self.structures):
            print(struct + '\t{0:4.5f}\t{1:4.5f}'.format(self.eos[i], self.mfe_energy-self.eos[i]))
        
        print(self.mfe_struct + '\t{0:4.5f}'.format(self.mfe_energy))


def main():
    parser = argparse.ArgumentParser(description='Design a tri-stable example same to Hoehner 2013 paper.')
    parser.add_argument("-p", "--progress", default=False, action='store_true', help='Show progress of optimization')
    parser.add_argument("-i", "--input", default=False, action='store_true', help='Read custom structures and sequence constraints from stdin')
    args = parser.parse_args()

    # define structures
    structures = []
    constraint = ""
    if (args.input):
        for line in sys.stdin:
            if re.match(re.compile("[\(\)\.]"), line, flags=0):
                structures.append(line.rstrip('\n'))
            elif re.match(re.compile("[ACGTUWSMKRYBDHVN]"), line, flags=0):
                constraint = line.rstrip('\n')
            elif re.search(re.compile("@"), line, flags=0):
                break;
    else:
        structures = ['((((....))))....((((....))))........',
            '........((((....((((....))))....))))',
            '((((((((....))))((((....))))....))))']
        constraint = 'NNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN'
    
    # construct dependency graph with these structures
    dg = rd.DependencyGraphMT(structures, constraint)
    
    print("\n".join(structures) + "\n" + constraint + "\n")
    # print the amount of solutions
    print('Maximal number of solutions: ' + str(dg.number_of_sequences()))
    # print the amount of connected components
    number_of_components = dg.number_of_connected_components()
    print('Number of Connected Components: ' + str(number_of_components))

    for i in range(0, number_of_components):
        print('[' + str(i) + ']' + str(dg.component_vertices(i)))
    print('')

    
    
    for d in xrange(0, 50000, 50):
        results = [];
        for n in range(0, 10):
            score = 0
            count = 0
            
            # randomly sample a initial sequence
            dg.set_sequence()
            result_seq = dg.get_sequence()
            # print this sequence with score
            score = calculate_objective(dg.get_sequence(), structures);
            #print dg.get_sequence() + '\t' + str(score)
            
            # mutate globally for 1000 times and print
            for i in range(0, d):
                # write progress
                if (args.progress):
                    sys.stdout.write("\rMutate ({0:02d}/{1:02d}): {2:7.0f}/{3:5.0f} from NOS: {4:7.0f}".format(d, n, i, count, dg.mutate_global()))
                    sys.stdout.flush()
                
                this_score = calculate_objective(dg.get_sequence(), structures);
                #print dg.get_sequence() + '\t' + str(this_score)
                
                if (this_score < score):
                    score = this_score
                    result_seq = dg.get_sequence()
                    count = 0
                else:
                    count += 1
                    if count > d:
                        break
            
            # finally print the result
            r = Result(result_seq, score, structures)
            #if (args.progress):
                #sys.stdout.write("\r                                                       \r")
                #sys.stdout.flush()
            #r.write()
            results.append(r)
        
        # process results
        eos_diff = []
        reached_mfe = 0
        for i in range(0, len(structures)):
            eos_diff.append(sum(r.eos[i]-r.mfe_energy for r in results)/len(results))
        for r in results:
            for s in r.structures:
                if (s == r.mfe_struct):
                    reached_mfe += 1
        
        if (args.progress):
            sys.stdout.write("\r                                                       \r")
            sys.stdout.flush()
        print(d, eos_diff, reached_mfe)


# objective function: eos(1)+eos(2)+eos(3) - 3 * gibbs + 1 * ((eos(1)-eos(2))^2 + (eos(1)-eos(3))^2 + (eos(2)-eos(3))^2)
def calculate_objective(sequence, structures):
    eos = []
    for struct in structures:
        eos.append(RNA.energy_of_struct(sequence, struct))
    
    gibbs = RNA.pf_fold(sequence)
    
    objective_difference_part = 0
    for i, value in enumerate(eos):
        for j in eos[i+1:]:
            objective_difference_part += pow(value - j, 2)
    
    return sum(eos) - len(eos) * gibbs[1] + 1 * objective_difference_part


if __name__ == "__main__":
    main()


