from state_class import State
class HDU:
    def __init__(self):
        self.E_to_E = 0   # 0  # this means transfer from memory to execute - addi to addi
        self.M_to_M = 0   # 1  # this means transfer from writeback to memory - ld to sd
        self.E_to_D = 0   # 2  # this means transfer from memory to decode - general RD-RS1 dependence
        self.M_to_D = 0   # 3  # this means transfer from writeback to decode - general
        self.M_to_E = 0   # 4  # this means transfer from writeback to execute - general

    # ind1 => Fetch, Decode, Exe, Ma, WB
    # para => RA, RB, RD
    def evaluate(self, ind1, ind2,forwardPaths, prevStates, isDataForwardingEnabled): # this is for data forwarding if possible
        isHazard = 0

        if ind1== 3 and ind2 == 4:
            if prevStates[4].RD == prevStates[3].RS2:
                isHazard = 1
                if(isDataForwardingEnabled == True):
                    prevStates[3].RM = prevStates[4].RY
                    self.M_to_M = prevStates[4].RY
                    forwardPaths.append(1)
        if ind1==2 and ind2 == 4:
            temp = 0
            if prevStates[2].RS1 == prevStates[4].RD:
                temp = 1
                if(isDataForwardingEnabled == True):
                    prevStates[2].RA = prevStates[4].RY
            if prevStates[2].RS2 == prevStates[4].RD:
                temp = 1
                if(isDataForwardingEnabled == True):
                    prevStates[2].RB = prevStates[4].RY
                    prevStates[2].RM = prevStates[4].RY
            if temp==1:
                isHazard = 1
                if(isDataForwardingEnabled == True):
                    self.M_to_E = prevStates[4].RY
                    forwardPaths.append(4)

        if ind1 == 2 and ind2 == 3:
            temp = 0
            if prevStates[2].RS1 == prevStates[3].RD:
                temp = 1
                if(isDataForwardingEnabled == True):
                    prevStates[2].RA = self.E_to_E = prevStates[3].RZ
            if prevStates[2].RS2 == prevStates[3].RD:
                temp = 1
                if(isDataForwardingEnabled == True):
                    prevStates[2].RB = prevStates[3].RZ
                    prevStates[2].RM = prevStates[3].RZ
            if temp:
                isHazard = 1
                if(isDataForwardingEnabled == True):
                    forwardPaths.append(0)
        
        if ind1 == 1 and ind2 == 4:
            temp = 0
            if prevStates[1].RS1 == prevStates[4].RD:
                temp = 1
                if(isDataForwardingEnabled == True):
                    prevStates[1].RS1Branch = prevStates[4].RY
            if prevStates[1].RS2 == prevStates[4].RD:
                temp = 1
                if(isDataForwardingEnabled == True):
                    prevStates[1].RS2Branch = prevStates[4].RY
            if temp:
                isHazard = 1
                if(isDataForwardingEnabled == True):
                    forwardPaths.append(3)

        if ind1 == 1 and ind2 == 3:
            temp = 0
            if prevStates[1].RS1 == prevStates[3].RD:
                temp = 1
                if(isDataForwardingEnabled == True):
                    prevStates[1].RS1Branch = prevStates[3].RZ
            if prevStates[1].RS2 == prevStates[3].RD:
                temp = 1
                if(isDataForwardingEnabled == True):
                    prevStates[1].RS2Branch = prevStates[3].RZ
            if temp:
                isHazard = 1
                if(isDataForwardingEnabled == True):
                    forwardPaths.append(2)
            
        
        return isHazard

    def isDataHazard(self, states, isDataForwardingEnabled):
        forwardPaths = []
        for i in range (5):
            if states[i]==None:
                states[i] = State(-1)
        newState = [states[0]]
        prevStates = states[:]
        # isHazard, toStall, whereToStall = [0,0,3]
        isHazard = 0
        stallParameters = [0,-1, -1]
        if(isDataForwardingEnabled == False):
            if(prevStates[1].opcode != 0):
                if(prevStates[4].opcode != 0):
                    c1 = self.evaluate(1,4,forwardPaths, prevStates,isDataForwardingEnabled)
                else: c1=0
                if(prevStates[3].opcode != 0):
                    c2 = self.evaluate(1,3,forwardPaths, prevStates,isDataForwardingEnabled)
                else: c2=0
                if(prevStates[2].opcode != 0):
                    c3 = self.evaluate(1,2,forwardPaths, prevStates,isDataForwardingEnabled)
                else: c3=0
            else: 
                c1=0; c2=0; c3=0; 
            isHazard = c1 | c2 | c3
            newState.extend(prevStates[1:])
            return [isHazard, [0, -1 ,-1], newState, []]
        prevStatesOpcode = [0]
        for i in range (1,5):
            prevStatesOpcode.append(int(str(prevStates[i].IR),16) & int("0x7f",16))
        # fetch, decode, exe, MA, WB
        if prevStatesOpcode[4]==3 and prevStatesOpcode[3]==35 and prevStates[4].RD >=1:
            isHazard = self.evaluate(3,4,forwardPaths, prevStates,isDataForwardingEnabled)
        
        if prevStates[4].RD >= 1:
            isHazard = self.evaluate(2,4,forwardPaths, prevStates,isDataForwardingEnabled)
        
        if prevStates[3].RD >= 1:
            if (prevStatesOpcode[3] == 3) and (prevStatesOpcode[2] == 35 and prevStates[2].RS1 == prevStates[3].RD):
                isHazard = 1
                stallParameters = [1, 2, 3]
            if (prevStatesOpcode[3] == 3) and (prevStatesOpcode[2]!=35 and (prevStates[2].RS1 == prevStates[3].RD or prevStates[2].RS2 == prevStates[3].RD)):
                isHazard = 1
                stallParameters = [1, 2, 3]
            if prevStatesOpcode[3]!=3:
                isHazard = self.evaluate(2,3, forwardPaths, prevStates,isDataForwardingEnabled)
        
        if prevStatesOpcode[1] in [99, 103]:
            # M to D forwarding
            if prevStates[4].RD >= 1:
                isHazard = self.evaluate(1,4, forwardPaths, prevStates,isDataForwardingEnabled)
            # E to D forwarding
            if prevStates[3].RD >=1:
                if prevStatesOpcode[3] in [3] and (prevStates[3].RD in [prevStates[1].RS1, prevStates[1].RS2]):
                    isHazard = 1
                    stallParameters = [1, 1, 3]
                else:
                    isHazard = self.evaluate(1,3,forwardPaths, prevStates,isDataForwardingEnabled)
            
            if prevStates[2].RD >=1:
                if (prevStates[2].RD in [prevStates[1].RS1, prevStates[1].RS2]):
                    isHazard = 1
                    stallParameters = [1, 1, 2]

        newState.extend(prevStates[1:])
        forwardPaths = list(set(forwardPaths))
        return [isHazard, stallParameters, newState, forwardPaths]