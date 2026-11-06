Tempest ARKNET tool

This is my vision for how we will use it in the future

By copying one folder into another repo (the folder shouldn’t be huge \- should be possible to share it though git)  
We should be able to call various commands using the AIs and APIs

These are the different calls

1. A function where given the location and time, gets back several requested figures (that are also listed, in a sequential manner) and gives them back.   
2. A version of function 2 \- but for monte carlo \- gives back the distribution type and the data to build the distribution (for now just set up the frame, Ill make this more integratable in the future \- for now just have a file with each distribution type in the folder, and also if you want allow the distributions to be empirically fitted.)  
3. Function 2 should have several settings \- setting 0 which gives standard distributions that account for model error for future predictions \- setting 1 which remove the accounting for model error \- setting 2 that give empirically fitted distributions for anything requested with error \- setting 3 that gives empirically fitted, without error accounted for  
4. There should be a third function which sets up coupling between requested parameters \- use the most effective coupling that fits with our design, or have several types of coupling with different settings the same way function 2 has them  
5. A “atmosphere” function for the terminal that given the date and location \- gives the inputs for atmosphere for the given percentile \- like if given 25% then gives the 25th percentile atmosphere \- mainly for RAS inputs (so default should just give what RAS takes in and if percentile is not mentioned it should give 15%, 50% and 85%) \- f clarification is added it can give additional parameters \- but not series data just single values like how RAS takes it. Should be easy to read and put into RAS. It should NOT be set up to actual get the percentiles, but rather the code should reorganize everything to make percentiles that go from “Worst” to “Best” flight conditions \- given the distribution for a day (error included if future) and gives the percentiles between those  
6. When building this, look at the flight\_sim repo and try to build code that is compatible to it with similar structure too that is easy to read and understand (Note: a lot has not been added to flight\_sim yet, like gusts and more. This is set up so we can use it when flight sim is complete, so dont worry about these things). 

The setup data getter, should have the different modes we already set up  
Using an what already exists for past data  
Using corrected predictions for current data  
Agian using corrected predictions for data within the next week or so   
Using recent data and predictions to correct longer term predictions   
Just using the AI above a certain threshold (when recent data and predictions are no longer helpful) 

These should be the settings.   
Adjust this plan to your liking, but try to keep the user facing items (like function calls and more) similar, but adjust it so this system maximizes its usage of what we have built, and works as effectively as possible, and is very useful for validating our rocket and monte carlo sims (getting the distributions for them) 