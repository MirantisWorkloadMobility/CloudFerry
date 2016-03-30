# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.


def accurate(flavors_list, max_ram, max_core):
    """
    This is implementation of bounded multiobjective multidimension knapsack
    solution with dynamic programming
    Good place to start with one dimensional problem:
        http://rosettacode.org/wiki/Knapsack_problem/Bounded#Python
    """

    # allocate huge 4-dimensional array, filled with zeros
    state = []
    for _ in range(len(flavors_list) + 1):
        i_array = []
        for ram in range(max_ram + 1):
            ram_array = []
            for core in range(max_core + 1):
                # for each state - we keep 2 objectives
                ram_array.append((0, 0))
            i_array.append(ram_array)
        state.append(i_array)

    # start filling the array
    for index in range(1, len(flavors_list) + 1):
        flavor_ram, flavor_core = flavors_list[index - 1][1:]
        for ram in range(1, max_ram + 1):
            for core in range(1, max_core + 1):
                if ram >= flavor_ram and core >= flavor_core:
                    previous_item = state[
                        index - 1][ram - flavor_ram][core - flavor_core]
                    current_item = state[index - 1][ram][core]
                    candidate_ram = previous_item[0] + flavor_ram
                    candidate_core = previous_item[1] + flavor_core
                    # we put item into knapsack
                    # only if we can improve both of objectives
                    if (candidate_ram >= current_item[0] and
                            candidate_core >= current_item[1]):
                        state[index][ram][core] = (candidate_ram,
                                                   candidate_core)
                    else:
                        state[index][ram][core] = state[index - 1][ram][core]
                else:
                    state[index][ram][core] = state[index - 1][ram][core]

    # backtrack the result
    result = []
    ram, core = max_ram, max_core
    for index in range(len(flavors_list), 0, -1):
        was_added = state[index][ram][core] != state[index - 1][ram][core]
        if was_added:
            result.append(flavors_list[index - 1])
            flavor_ram, flavor_core = flavors_list[index - 1][1:]
            ram -= flavor_ram
            core -= flavor_core
    return result


def fast(flavors_list, max_ram, max_core):
    """
    This is implementation of unbounded multiobjective multidimensional
    knapsack problem solution
    Good place to start:
    http://rosettacode.org/wiki/Knapsack_problem/Unbounded/Python_dynamic_programming#DP.2C_multiple_size_dimensions
    """

    # prepare initial state
    state = []
    for ram in range(max_ram + 1):
        state.append([[[0, 0], [0 for i in flavors_list]]
                      for _ in range(max_core + 1)])

    # find solution
    for i, fl_obj in enumerate(flavors_list):
        flavor_count, flavor_ram, flavor_core = fl_obj[1:]
        for ram in range(flavor_ram, max_ram + 1):
            for core in range(flavor_core, max_core + 1):
                prev_state = state[ram - flavor_ram][core - flavor_core]
                candidate_ram = prev_state[0][0] + flavor_ram
                candidate_core = prev_state[0][1] + flavor_core
                if prev_state[1][i] < flavor_count:
                    if (state[ram][core][0][0] <= candidate_ram and
                            state[ram][core][0][1] <= candidate_core):
                        state[ram][core] = [
                            [candidate_ram, candidate_core], prev_state[1][:]]
                        state[ram][core][1][i] += 1
    return state[max_ram][max_core][1]
