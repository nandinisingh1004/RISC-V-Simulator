from collections import defaultdict
import math 

class State:
    def __init__(self, pc=0):
        self.PC = pc
        self.reset()
    
    def reset(self):
        self.message=""
        self.ALUOp=[0]*15
        self.RS1 = -1
        self.RS2 = -1
        self.fun3 = -1
        self.fun7 = -1
        self.RD = 0
        self.RM = 0
        self.RZ = 0
        self.RY = 0
        self.RA = 0
        self.RB = 0
        self.IR = 0
        self.MAR = 0
        self.MDR = 0
        self.immed=0
        self.opcode = 0
        self.PC_temp = 0
        self.RF_Write = 0
        self.MuxMA_select = 0
        self.MuxB_select = 0
        self.MuxY_select = 0
        self.Mem_Write = 0
        self.Mem_Read = 0
        self.MuxPC_select = 0
        self.MuxINC_select = 0
        self.numBytes = 0
        self.predictionOutcome = 0
        self.predictionPC = -1
        self.RS1Branch = -1
        self.RS2Branch = -1
        self.PC1 = self.PC

class BTB:
    def __init__(self):
        self.Btb_table = defaultdict(lambda: -1)
        self.P_state = 0

    def isPresent(self, PC):   # isEntered
        if self.Btb_table[PC] == -1:
            return 0
        else:
            return 1
    
    def store(self, PC, targetAddress):
        self.Btb_table[PC] = targetAddress
    
    def prediction(self, PC):
        return True
    
    def getTarget(self, PC):
        return self.Btb_table[PC]


class CPU:
    def __init__(self, isPipelined ,predictionEnabled = 1):
        # self.dataMemory = defaultdict(lambda : [[0,0,0,0] for i in range(blockSize)])
        # self.instructionMemory = defaultdict(lambda: [0,0,0,0])
        #to change instructionMemory
        self.reg = [0]*32
        self.reg[2] = int("0x7FFFFFF0",16) # sp - STACK POINTER
        self.reg[3] = int("0x10000000",16) # pointer to begining of data segment
        self.isPipelined = isPipelined
        
    def validateInstruction(self,y):
        if len(y)!=2:
            return False
        addr,data = y[0],y[1]
        if addr[:2]!='0x' or data[:2]!='0x':
            return False
        try:
            temp = int(addr,16)
            temp1 = int(data,16)
        except:
            return False
        return True
    

    def readInstructionMem(self,pc,instrCacheMemObj,mainMemoryObject,numMisses,numHits):
        MAR = hex(pc)
        ans = instrCacheMemObj.readCache(MAR,mainMemoryObject,numMisses,numHits)
        if(ans[0]==-1 and ans[1]==-1 and ans[2]==-1 and ans[3]==-1):
            return "Invalid"
        newans = ""
        x=len(ans)
        for i in range(len(ans)):
            newans += str(ans[x-1-i])
        newans = '0x'+newans
        return newans
        
    def sra(self, number,times):     #correct function
        bx = bin(number)[2:]
        if len(bx)<32 or bx[0]=='0':
            return number>>times
        else:
            ans = '1'*times + bx[:32-times]
            twosCompli = [str(1-int(i)) for i in ans[1:]]
            twosCompli = (''.join(twosCompli))
            twosCompli = - (int(twosCompli,2) + 1)
            return twosCompli
 
    
    def ProcessorMemoryInterface(self, state, cacheMemoryObject,mainMemoryObject,numMisses,numHits):
        # Set MAR in Fetch
        if state.MuxMA_select == 0:
            if state.Mem_Read == 1:
                word = cacheMemoryObject.readCache(state.MAR,mainMemoryObject,numMisses,numHits)
                temp = word[:state.numBytes]
                temp.reverse()
                ans = '0x'
                for i in temp:
                    curr =  hex(i)[2:]
                    ans += '0'*(2-len(curr)) + curr
                return ans
            elif state.Mem_Write == 1:
                cacheMemoryObject.writeCache(state.MAR,state.MDR,mainMemoryObject)
                return '0x1'

    def GenerateControlSignals(self,reg_write,MuxB,MuxY,MemRead,MemWrite,MuxMA,MuxPC,MuxINC,numB,state):

        state.RF_Write = reg_write
        state.MuxB_select = MuxB
        state.MuxY_select = MuxY
        state.Mem_Write = MemWrite
        state.Mem_Read = MemRead
        state.MuxMA_select = MuxMA
        state.MuxPC_select = MuxPC
        state.MuxINC_select = MuxINC
        state.numBytes = numB

    def extendSign(self,num, numBits):
        if(num & 2**(numBits-1) == 0):
            return num
        num = num ^ (2**numBits-1)
        num += 1
        num *= (-1)
        return num

    def ImmediateSign(self,num,state):
    
        if(state.immed & 2**(num-1) == 0):
            return
        state.immed = state.immed ^ (2**num-1)
        state.immed += 1
        state.immed *= (-1)
    
    def Fetch(self,state,btb,mainMemoryObject,instrCacheMemObj,numMisses,numHits):
        pc=state.PC
        newPC = -1
        ir=self.readInstructionMem(pc,instrCacheMemObj,mainMemoryObject,numMisses,numHits)
        if(ir=="Invalid"):
            return None
        state.IR=ir
        opcode = int(str(state.IR),16) & int("0x7f",16)
        state.opcode = opcode
        state.RS1 = (int(state.IR,16) & int('0xF8000',16)) >> 15 
        state.RS2 = (int(state.IR,16) & int('0x1F00000',16)) >> 20 
        if (opcode in [99, 103, 111]):
            if (btb.isPresent(pc)):
                newPC = btb.getTarget(pc)
        state.predictionPC = newPC
        state.PC_Temp=state.PC+4
        return state

    def Decode(self,state, btb):    
        newPC=0    
        controlHazard=0
        state.opcode = int(str(state.IR),16) & int("0x7f",16)
        state.fun3 = (int(str(state.IR),16) & int("0x7000",16)) >> 12
        
        # R format - (add,srl,sll,sub,slt,xor,sra,and,or,mul, div, rem)
        # R format - (0110011)  
        # I format - (lb-0,lh-1,lw-2)(addi-0, andi-7, ori-6,)(jalr-0)
        # I format - (0000011)(0010011)(1100111)
        # S format - (sb, sw, sh)
        # S format - (0100011) f3 - sb - 000, sh - 001, sw - 010
        # SB format - beq, bne, bge, blt
        # SB format - (1100011) f3 - beq - 000, bne - 001, blt - 100, bge - 101
        # U format - a
        # UJ format - jal-1101111

        if state.opcode==int("0110011",2): # R format
            self.GenerateControlSignals(1, 0, 0, 0, 0, 0, 1, 0, 4,state)
            state.RD = (int(state.IR,16) & int('0xF80',16)) >> 7 
            state.RS1 = (int(state.IR,16) & int('0xF8000',16)) >> 15 
            state.RS2 = (int(state.IR,16) & int('0x1F00000',16)) >> 20 
            state.fun7 = (int(state.IR,16) & int('0xFE000000',16)) >> 25
            if state.fun3 == 0:  # add/sub/mul
                if state.fun7 == 0: # add 
                    state.ALUOp[0]=1
                    state.message = "This is ADD instruction."
                elif state.fun7 == 32: # subtract
                    state.ALUOp[1]=1
                    state.message = "This is SUB instruction."
                elif state.fun7==1: # mul
                    state.ALUOp[3]=1 
                    state.message = "This is MUL instruction."
                else:
                    print("Invalid Func7 for Add/Sub")                    
                    exit(1)
            elif state.fun3==7: # and
                state.message = "This is AND instruction."
                if state.fun7==0:
                    state.ALUOp[10]=1
                else:
                    print("Invalid Fun7 for AND")                    
                    exit(1)
            elif state.fun3 == 6: # or/remainder
                if state.fun7==0: # or
                    state.message = "This is OR instruction."
                    state.ALUOp[9]=1
                elif state.fun7==1: # remainder
                    state.ALUOp[4]=1
                    state.message = "This is REMAINDER instruction."
                else:
                    print("Invalid Func7 for OR/REM")                    
                    exit(1)
            elif state.fun3 == 1: # sll - shift_left
                if state.fun7==0:
                    state.ALUOp[6]=1
                    state.message = "This is SLL instruction."
                else:
                    print("Invalid Func7 for SLL")                    
                    exit(1)
            elif state.fun3 == 2: # slt - set_if_less_than
                state.message = "This is SLT instruction."
                if state.fun7==0:
                    state.ALUOp[11]=1
                else:
                    print("Invalid Func7 for SLT")                    
                    exit(1)
            elif state.fun3 == 5: # srl/sra
                if state.fun7==32: # shift_ri_ari
                    state.message = "This is SRA instruction."
                    state.ALUOp[7]=1
                elif state.fun7==0: #shift_ri_lo
                    state.message = "This is SRL instruction."
                    state.ALUOp[8]=1
                else:
                    print("Invalid Func7 for SRA/SRL")                    
                    exit(1)
            elif state.fun3 == 4: #xor/div
                if state.fun7==0: # xor
                    state.message = "This is XOR instruction."
                    state.ALUOp[5]=1
                elif state.fun7==1: #div
                    state.message = "This is DIV instruction."
                    state.ALUOp[2]=1
                else:
                    print("Invalid fun7 for R format instruction")                    
                    exit(1)
            else:
                print("Invalid func3 for R format instruction")                
                exit(1)
            #setting ra rb rm -------------------------------------------------
            state.RA = self.reg[state.RS1]
            state.RB = self.reg[state.RS2] 
            state.RM = state.RB        # ---- DON'T CARES
            # -----------------------------------------------------------------
    
        elif state.opcode==int("0000011",2) or state.opcode==int("0010011",2) or state.opcode==int("1100111",2): # I format
            state.RD = (int(state.IR,16) & int('0xF80',16)) >> 7 
            state.RS1 = (int(state.IR,16) & int('0xF8000',16)) >> 15 
            state.immed = (int(state.IR,16) & int('0xFFF00000',16)) >> 20

            #  ADDING CONSTRAINTS ON IMMEDIATE
            if state.immed>2047:
                state.immed -= 4096
            
            if state.opcode==int("0000011",2): # lb/lh/lw
                state.ALUOp[0]=1
                if state.fun3 == 0: #lb
                    state.message = "This is LB instruction."
                    self.GenerateControlSignals(1,1,1,1,0,0,1,0,1,state)
                elif state.fun3 == 1: #lh
                    state.message = "This is LH instruction."
                    self.GenerateControlSignals(1,1,1,1,0,0,1,0,2,state)
                elif state.fun3 == 2: #lw
                    state.message = "This is LW instruction."
                    self.GenerateControlSignals(1,1,1,1,0,0,1,0,4,state)
                else: 
                    print("Invalid fun3 for I format instruction")                   
                    exit(1)
                #setting RA, RB, RM 
                state.RA = self.reg[state.RS1]
                # RB = reg[RS2]   ---- DON'T CARES
                # RM = RB         ---- DON'T CARES
            elif state.opcode==int("0010011",2): #addi/andi/ori
                self.GenerateControlSignals(1,1,0,0,0,0,1,0,4,state)
                if state.fun3==0:#addi
                    state.message = "This is ADDI instruction."
                    state.ALUOp[0]=1
                elif state.fun3==7:#andi
                    state.message = "This is ANDI instruction."
                    state.ALUOp[10]=1
                elif state.fun3==6:#ori
                    state.message = "This is ORI instruction."
                    state.ALUOp[9]=1
                else:
                    print("Invalid fun3 for I format instruction")                     
                    exit(1)
                #setting RA, RB, RM
                state.RA = self.reg[state.RS1]
                # RB = reg[RS2]   ---- DON'T CARES
                # RM = RB         ---- DON'T CARES
            elif state.opcode==int("1100111",2): #jalr 
                state.message = "This is JALR instruction."
                self.GenerateControlSignals(1,0,2,0,0,0,0,1,4,state)
                if state.fun3==0:
                    state.ALUOp[0]=1
                else:
                    print("Invalid fun3 for I format instruction")                     
                    exit(1)
                #setting RA, RB, RM
                state.RA = self.reg[state.RS1]
                if(state.RS1Branch!=-1):
                    state.RA = state.RS1Branch
                # RB = reg[RS2]   ---- DON'T CARES
                # RM = RB         ---- DON'T CARES
                btb.store(state.PC, state.RA)
                controlHazard = -1
                newPC = btb.getTarget(state.PC)
        
        # S format
        elif state.opcode==int("0100011",2): # S format
            state.RS1 = (int(str(state.IR),16) & int("0xF8000",16)) >> 15
            state.RS2 = (int(str(state.IR),16) & int("0x1F00000",16)) >> 20
            immed4to0 = (int(str(state.IR),16) & int("0xF80",16)) >> 7
            immed11to5 = (int(str(state.IR),16) & int("0xFE000000",16)) >> 25
            state.immed = immed4to0 | immed11to5
            self.ImmediateSign(12,state)
            state.ALUOp[0]=1
            if state.fun3 == int("000",2): # sb
                state.message = "This is SB instruction."
                self.GenerateControlSignals(0,1,1,0,1,0,1,0,1,state)
            elif state.fun3 == int("001",2): # sh
                self.message = "This is SH instruction."
                self.GenerateControlSignals(0,1,1,0,1,0,1,0,2,state)
            elif state.fun3 == int("010",2): # sw
                state.message = "This is SW instruction."
                self.GenerateControlSignals(0,1,1,0,1,0,1,0,4,state)
            else:
                print("Invalid fun3 for S format instruction")                 
                exit(1)
            #setting RA, RB, RM -------------------------------------------------
            state.RA = self.reg[state.RS1]
            state.RB = self.reg[state.RS2]
            if state.RS1Branch != -1:
                state.RA = state.RS1Branch
            if state.RS2Branch != -1:
                state.RB = state.RS2Branch
            state.RM = state.RB

        elif state.opcode==int("1100011",2): # SB format
            state.RS1 = (int(state.IR, 16) & int("0xF8000", 16)) >> 15
            state.RS2 = (int(state.IR, 16) & int("0x1F00000", 16)) >> 20
            state.RA = self.reg[state.RS1]
            state.RB = self.reg[state.RS2]
            imm1 = (int(state.IR, 16) & int("0xF80", 16)) >> 7
            imm2 = (int(state.IR, 16) & int("0xFE000000", 16)) >> 25
            state.immed = 0
            state.immed = state.immed | ((imm1 & int("0x1E", 16)) >> 1)
            state.immed = state.immed | ((imm2 & int("0x3F", 16)) << 4)
            state.immed = state.immed | ((imm1 & 1) << 10)
            state.immed = state.immed | (((imm2 & int("0x40", 16)) >> 6) << 11)
            self.ImmediateSign(12,state)
            state.immed *= 2
            # Setting control Signals
            if state.RS1Branch != -1:
                state.RA = state.RS1Branch
            if state.RS2Branch != -1:
                state.RB = state.RS2Branch

            if state.fun3 == 0:
                state.message = "This is BEQ instruction."
                state.ALUOp[12] = 1
            elif state.fun3 == 1:
                state.message = "This is BNE instruction."
                state.ALUOp[13] = 1
            elif state.fun3 == 4:
                state.message = "This is BLT instruction."
                state.ALUOp[11] = 1
            elif state.fun3 == 5:
                state.message = "This is BGE instruction."
                state.ALUOp[14] = 1
            else:                
                print("Invalid fun3 for SB format instruction")                 
                exit(1)
            self.GenerateControlSignals(0,0,0,0,0,0,1,1,0,state)
            self.Execute(state)
            target = state.PC + state.immed
            if(btb.isPresent(state.PC) == 0):
                btb.store(state.PC, target)
                if(state.RZ == 0):
                    controlHazard = 0
                else:
                    controlHazard = -1
                    newPC = target
            else:
                if(state.RZ == 0):
                    controlHazard = 1

        elif state.opcode==int("0010111",2) or state.opcode==int("0110111",2): # U type
            state.RD = (int(state.IR, 16) & int("0xF80", 16)) >> 7
            state.immed = (int(state.IR, 16) & int("0xFFFFF000", 16)) >> 12
            self.ImmediateSign(20,state)
            if state.opcode == int("0010111", 2): # A                
                state.ALUOp[0] = 1
                state.RA = state.PC
                state.immed = state.immed << 12
                state.message = "This is an AUIPC Instruction"
            else: #L                
                state.ALUOp[6] = 1
                state.RA = state.immed
                state.immed = 12
                state.message = "This is an LUI Instruction"
            self.GenerateControlSignals(1,1,0,0,0,0,1,0,0,state)

        elif state.opcode==int("1101111",2): # UJ format
            state.message = "This is JAL instruction."
            state.RD = (int(state.IR, 16) & int("0xF80", 16)) >> 7
            immed_tmp = (int(state.IR, 16) & int("0xFFFFF000", 16)) >> 12
            state.immed = 0
            state.immed = state.immed | ((immed_tmp & int("0x7FE00", 16)) >> 9)
            state.immed = state.immed | ((immed_tmp & int("0x100", 16)) << 2)
            state.immed = state.immed | ((immed_tmp & int("0xFF", 16)) << 11)
            state.immed = state.immed | (immed_tmp & int("0x80000", 16))
            self.ImmediateSign(20,state)
            state.immed *= 2
            state.ALUOp[12] = 1
            state.RA = 0
            state.RB = 0
            self.GenerateControlSignals(1,0,2,0,0,0,1,1,0,state)
            if btb.isPresent(state.PC) == 0:
                btb.store(state.PC, state.PC + state.immed)
                controlHazard = -1
                newPC = btb.getTarget(state.PC)
        else:
            print("Invalid Opcode !!!")
            exit(1)
        if state.RS1Branch != -1:
            state.RA = state.RS1Branch
        if state.RS2Branch != -1:
            state.RB = state.RS2Branch
        # if the instruction is identified correctly, print which instruction is it
        return controlHazard, newPC

    def Execute(self,state):
        operation = state.ALUOp.index(1)
        InA = state.RA
        if(state.MuxB_select == 1):
            InB = state.immed
        else:
            InB = state.RB
        if(operation == 0): #add
            state.RZ = InA + InB
        elif(operation == 1): #sub
            state.RZ = InA - InB
        elif(operation == 2): #div
            if(InB == 0):
                exit(1)
            state.RZ = int(InA/InB)
        elif(operation == 3): #mul
            state.RZ = InA*InB
        elif(operation == 4): #remainder
            if(InB == 0):
                exit(1)
            state.RZ = InA%InB
        elif(operation == 5): #xor
            state.RZ = InA^InB
        elif(operation == 6): #shift_left
            if (InB<0):
                exit(1)
            state.RZ = InA<<InB
        elif(operation == 7): #shift_right_ari 
            state.RZ = self.sra(InA, InB)
            pass
        elif(operation == 8): #shift_ri_lo  
            if (InB<0):
                exit(1)
            state.RZ = InA>>InB
        elif(operation == 9): #or  
            state.RZ = (InA|InB)
        elif(operation == 10): #and  
            state.RZ = (InA&InB)
        elif(operation == 11): #less_than 
            state.RZ = int(InA<InB)
            state.MuxINC_select = state.RZ
        elif(operation == 12): #equal  
            state.RZ = int(InA==InB)
            state.MuxINC_select = state.RZ
        elif(operation == 13): #not_equal  
            state.RZ = int(InA!=InB)
            state.MuxINC_select = state.RZ
        elif(operation == 14): #greater_than_equal_to  
            state.RZ = int(InA>=InB)
            state.MuxINC_select = state.RZ

    def IAG(self,state):
        
        if(state.MuxPC_select == 0):
            state.PC1 = state.RA
        else:
            if(state.MuxINC_select == 0):
                state.PC1 = state.PC + 4
            else:
                state.PC1 = state.PC + state.immed
    
    def MemoryAccess(self,state,dataCacheMemObj,mainMemoryObject,numMisses,numHits):
        if self.isPipelined == 0:
            self.IAG(state)
        if state.MuxY_select == 0:
            state.RY = state.RZ
        elif state.MuxY_select == 1:
            state.MAR = state.RZ
            state.MDR = state.RM
            state.RY = int(self.ProcessorMemoryInterface(state,dataCacheMemObj,mainMemoryObject,numMisses,numHits),16)
            if state.RY > 2**31 - 1:
                state.RY = -(2**32 - state.RY)
        elif state.MuxY_select == 2:
            state.RY = state.PC_Temp

    def RegisterUpdate(self,state):
        if state.RF_Write == 1 and state.RD != 0:
            self.reg[state.RD] = state.RY


class MainMemory:
    def __init__(self, blockSize): 
        self.dataMemory = defaultdict(lambda : [[-1,-1,-1,-1] for i in range(blockSize)])
        self.instructionMemory = defaultdict(lambda : [[-1,-1,-1,-1] for i in range(blockSize)])

    def validateDataSegment(self,y):
        if len(y)!=2:
            return False
        addr,data = y[0],y[1]
        if addr[:2]!='0x' or data[:2]!='0x':
            return False
        try:
            if int(addr,16)<int("0x10000000",16):
                return False
            int(data,16)
        except:
            return False 
        return True

    
    def readFile(self, blockOffset): # blockOffset means number of bits in BO
        try:
            mcFile = open("Phase3/input.mc","r")
        except:
            print("File Not Found!")
            return
        # load the data segment
        flag = 0
        andVal = 2**32-2**blockOffset
        for x in mcFile:
            #creating a hashmap, data segment stored
            y = x.split('\n')[0].split()
            if '$' in y[1]:
                flag = 1  
                continue  
            y[1] = y[1].lower()
            newY = int(y[0],16) & andVal
            indexInBlock = int(y[0],16) & (2**blockOffset - 1)
            indexInBlock = indexInBlock//4
            if flag==1:
                if self.validateDataSegment(y)==False:
                    print("ERROR : Invalid Data Segment format in the input.mc file")
                    exit(1)

                self.dataMemory[newY][indexInBlock][0] = (int(y[1],16) & int('0xFF',16)) # the LSB is stored in the zeroth position of the array
                self.dataMemory[newY][indexInBlock][1] = (int(y[1],16) & int('0xFF00',16))>>8
                self.dataMemory[newY][indexInBlock][2] = (int(y[1],16) & int('0xFF0000',16))>>16
                self.dataMemory[newY][indexInBlock][3] = (int(y[1],16) & int('0xFF000000',16))>>24 # the MSB is stored in the third position of the array

            if flag==0:
                if self.validateInstruction(y)== False:
                    print("ERROR : Invalid Instruction format in the input.mc file")                    
                    exit(1)
                
                for i in range (4):
                    self.instructionMemory[newY][indexInBlock][i] = hex((int(y[1],16) & int('0xFF'+'0'*(2*i),16))>>(8*i))[2:]
                    self.instructionMemory[newY][indexInBlock][i] = '0'*(2-len(self.instructionMemory[newY][indexInBlock][i])) + self.instructionMemory[newY][indexInBlock][i]
                    self.instructionMemory[newY][indexInBlock][i] = self.instructionMemory[newY][indexInBlock][i].lower()

    def validateInstruction(self,y):
        if len(y)!=2:
            return False
        addr,data = y[0],y[1]
        if addr[:2]!='0x' or data[:2]!='0x':
            return False
        try:
            temp = int(addr,16)
            temp1 = int(data,16)
        except:
            return False
        return True

class InstrCacheMemory:
    def __init__(self, cacheSize, blockSize, cacheAssociativity):       

        self.cacheAssociativity = cacheAssociativity

        self.numSets = cacheSize // blockSize
        self.numWords = blockSize//4
        self.numSets = self.numSets // cacheAssociativity
        self.indexSize = math.log2(self.numSets)
        if(self.indexSize-int(self.indexSize)!=0): self.indexSize += 1
        self.indexSize = int(self.indexSize)
        self.blockOffsetSize = math.log2(blockSize)
        if(self.blockOffsetSize-int(self.blockOffsetSize)!=0): self.blockOffsetSize += 1
        self.blockOffsetSize = int(self.blockOffsetSize)
        self.tagSize = 32 - self.indexSize - self.blockOffsetSize

        self.tagArray = [[0 for i in range(self.cacheAssociativity)] for j in range(self.numSets)]
        self.instArray = [[[[0,0,0,0] for k in range(self.numWords)] for i in range(self.cacheAssociativity)] for j in range(self.numSets)]
        self.validBit = [[[0 for k in range(self.numWords)] for i in range(self.cacheAssociativity)] for j in range(self.numSets)]
        self.forLRU = [[0 for i in range(self.cacheAssociativity)] for j in range(self.numSets)]
        self.victim = -1
        self.current = -1

    def LRU(self,index):
        for i in range(self.cacheAssociativity):
            if(self.forLRU[index][i]==0):
                if(self.validBit[index][i].count(1)>0):
                    self.victim = i+1
                else:
                    self.victim = 0
                return i
        return 0

    def readCache(self,address,mainMemoryObject,numMisses,numHits): # address is a hexadecimal string
        address = int(address,16)
        blockOffset = address &  (2**self.blockOffsetSize - 1) 
        index = address &  ( (2**self.indexSize - 1) << self.blockOffsetSize) 
        tag = address &  ( (2**self.tagSize - 1) << (self.blockOffsetSize + self.indexSize)) 
        index = index >> self.blockOffsetSize
        self.current = index + 1
        tag = tag >> (self.blockOffsetSize + self.indexSize)

        for i in range(self.cacheAssociativity):
            if(tag == self.tagArray[index][i]):
                if(self.validBit[index][i][blockOffset//4]==0): continue
                numHits[0]+=1
                return self.instArray[index][i][blockOffset//4]
        numMisses[0] += 1
        var = address & (2**32 - 2**self.blockOffsetSize)
        block = mainMemoryObject.instructionMemory[var]
        word = block[blockOffset//4]
        storeIndex = self.LRU(index)
        self.forLRU[index][storeIndex] = self.cacheAssociativity-1
        self.instArray[index][storeIndex] = block
        self.tagArray[index][storeIndex] = tag
        for i in range(self.cacheAssociativity):
            if(self.forLRU[index][i]!=0 and i != storeIndex): self.forLRU[index][i]-=1
        for i in range(self.numWords):
            if(self.instArray[index][storeIndex][i]!=[-1,-1,-1,-1]):
                self.validBit[index][storeIndex][i]=1
        return word

class DataCacheMemory:
    def __init__(self, cacheSize, blockSize, cacheAssociativity):
        # make a local variable fo the MainMemory class

        self.cacheAssociativity = cacheAssociativity

        self.numSets = cacheSize // blockSize
        self.numWords = blockSize//4
        self.numSets = self.numSets // cacheAssociativity
        self.indexSize = math.log2(self.numSets)
        if(self.indexSize-int(self.indexSize)!=0): self.indexSize += 1
        self.indexSize = int(self.indexSize)
        self.blockOffsetSize = math.log2(blockSize)
        if(self.blockOffsetSize-int(self.blockOffsetSize)!=0): self.blockOffsetSize += 1
        self.blockOffsetSize = int(self.blockOffsetSize)
        self.tagSize = 32 - self.indexSize - self.blockOffsetSize

        self.tagArray = [[0 for i in range(self.cacheAssociativity)] for j in range(self.numSets)]
        self.dataArray = [[[[0,0,0,0] for k in range(self.numWords)] for i in range(self.cacheAssociativity)] for j in range(self.numSets)]
        self.validBit = [[[0 for k in range(self.numWords)] for i in range(self.cacheAssociativity)] for j in range(self.numSets)]
        self.forLRU = [[0 for i in range(self.cacheAssociativity)] for j in range(self.numSets)]
        self.victim = -1
        self.current = -1

    def LRU(self,index):
        for i in range(self.cacheAssociativity):
            if(self.forLRU[index][i]==0):
                
                self.victim = i+1
                return i
        return 0

    def readCache(self,address,mainMemoryObject,numMisses, numHits):
        blockOffset = address &  (2**self.blockOffsetSize - 1) 
        index = address &  ( (2**self.indexSize - 1) << self.blockOffsetSize) 
        tag = address &  ( (2**self.tagSize - 1) << (self.blockOffsetSize + self.indexSize)) 
        index = index >> self.blockOffsetSize
        tag = tag >> (self.blockOffsetSize + self.indexSize)
        self.current = index + 1

        for i in range(self.cacheAssociativity):
            if(tag == self.tagArray[index][i]):
                if(self.validBit[index][i][blockOffset//4]==0): continue
                numHits[0]+=1
                return self.dataArray[index][i][blockOffset//4]
        numMisses[0] += 1
        var = address & (2**32 - 2**self.blockOffsetSize)
        block = mainMemoryObject.dataMemory[var]
        word = block[blockOffset//4]
        storeIndex = self.LRU(index)
        self.forLRU[index][storeIndex] = self.cacheAssociativity-1
        self.dataArray[index][storeIndex] = block
        self.tagArray[index][storeIndex] = tag
        for i in range(self.cacheAssociativity):
            if(self.forLRU[index][i]!=0 and i != storeIndex): self.forLRU[index][i]-=1
        for i in range(self.numWords):
            if(self.dataArray[index][storeIndex][i]!=[-1,-1,-1,-1]):
                self.validBit[index][storeIndex][i]=1
        return word

    def writeCache(self,address,value,mainMemoryObject):
        val=[0,0,0,0]
        val[0] = (value & int('0xFF',16))
        val[1] = (value & int('0xFF00',16))>>8
        val[2] = (value & int('0xFF0000',16))>>16
        val[3] = (value & int('0xFF000000',16))>>24
        blockOffset = address &  (2**self.blockOffsetSize - 1) 
        index = address &  ( (2**self.indexSize - 1) << self.blockOffsetSize) 
        tag = address &  ( (2**self.tagSize - 1) << (self.blockOffsetSize + self.indexSize)) 
        index = index >> self.blockOffsetSize
        tag = tag >> (self.blockOffsetSize + self.indexSize)
        self.current = index + 1

        for i in range(self.cacheAssociativity):
            if(tag == self.tagArray[index][i]):
                self.dataArray[index][i][blockOffset//4]=val
                self.validBit[index][i][blockOffset//4]=1
                break
        
        # implementing write through with no write-allocate
        var = address & (2**32 - 2**self.blockOffsetSize)
        mainMemoryObject.dataMemory[var][blockOffset//4] = val
