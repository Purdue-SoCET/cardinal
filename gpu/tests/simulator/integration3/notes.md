notes

Need to change:

Update sm launch process with the new tbs stuff and the new sm from bin tbs stuff we set Update
Replace the SM class with launch kernel or something, because its not technically an sm class. Can subdivide it into two pieces; sm class, then a launch class with the tbs + sm classes as needed.
Per run, instantiate multiple versions of this with one tbs + sm with different configurations within the SM.
Update dcache with the changes from yesterday. 
Generate more graphs for the poster.
Run workloads for 1024 pixel, triangle, then maybe 2048.
What microarchiectural metrics do we want to present? 
ex. scheduler: different scheduling policy if its functional, diff arbitration from the memory controller, diff buffe sizes in issue + wb stages, ld/st execution buffer + dcache mods