Condensation
------------

Condensation is simply creating a scenario file that will be used during
the Evacuation phase. It is done within a single cloud and is meant to
figure out how to minimize the number of physical nodes handling the
total workload. Condensation is a tricky and slow task to do manually but
is fairly simple to do with CloudFerry. Much of the difficulty of doing
things manually comes from the Knapsack Problem which can be solved with
a little math but much like all things that can be solved with math,
it's easier and better to let the machines get on with the adding up
and leave the contemplation of larger issues to the working thinkers.


The Knapsack Problem
^^^^^^^^^^^^^^^^^^^^

The knapsack problem simply stated is:

    Given a set of items, each with a mass and a value, determine the number
    of each item to include in a collection so that the total weight is less
    than or equal to a given limit and the total value is as large as possible.

It derives its name from the problem faced by someone who is constrained by a
fixed-size *knapsack* and must fill it with the most valuable items. There are
well known mathematical and algorithmic solutions to the problem.


.. image:: images/knapsack.png
    :align: center


When the condensation feature is executed it will not make any
changes to the cloud. It will simply output a file which will define
the sequence and placement of VM's that the Evacuation phase will
execute against. Evacuation is run separately from condensation making
the Condensation operation purely informative if not followed up by
Evacuation. The scenario file that is generated can be modified before
Evacuation is run in order to accommodate specific needs or used as is.
