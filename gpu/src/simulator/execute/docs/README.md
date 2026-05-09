# Cardinal Cx01 Simulator: Execute Stage
> **Tip:** Use `Ctrl + Shift + V` in VS Code to render and view this Markdown file
- [Cardinal Cx01 Simulator: Execute Stage](#cardinal-cx01-simulator-execute-stage)
  - [Overview](#overview)
    - [Terminology](#terminology)
      - [Distinguishing between a Functional Unit and Functional Subunit](#distinguishing-between-a-functional-unit-and-functional-subunit)
      - [Python/Object-Oriented Programming Terms](#pythonobject-oriented-programming-terms)
      - [Python/Object-Oriented Programming Resrouces](#pythonobject-oriented-programming-resrouces)
    - [Essential Data Structures](#essential-data-structures)
      - [`Instruction` Class](#instruction-class)
      - [`Bits` Class and the `bitstring` Library](#bits-class-and-the-bitstring-library)
  - [`ExecuteStage` Class](#executestage-class)
    - [Creating an Instance of the `ExecuteStage` class](#creating-an-instance-of-the-executestage-class)
      - [`create_pipeline_stage()` Method](#create_pipeline_stage-method)
    - [`compute()` Method](#compute-method)
    - [`tick()` Method](#tick-method)
      - [1. Receives the instruction from the Issue Stage](#1-receives-the-instruction-from-the-issue-stage)
      - [2. Calls the `tick()` methods of the `FunctionalUnit` instances](#2-calls-the-tick-methods-of-the-functionalunit-instances)
      - [3. Pushes instructions with completed computations to the Writeback Buffer/Writeback Stage](#3-pushes-instructions-with-completed-computations-to-the-writeback-bufferwriteback-stage)
  - [`FunctionalUnit` Class](#functionalunit-class)
    - [`compute()` Method](#compute-method-1)
    - [`tick()` Method](#tick-method-1)
    - [Implemented Subclasses](#implemented-subclasses)
      - [IntUnit](#intunit)
      - [FloatUnit](#floatunit)
      - [SpecialUnit](#specialunit)
      - [MemBranchJumpUnit](#membranchjumpunit)
  - [`FunctionalSubUnit` Class](#functionalsubunit-class)
    - [`compute()` Method](#compute-method-2)
    - [`tick()` Method](#tick-method-2)
    - [Implemented Subclasses](#implemented-subclasses-1)
      - [`Ldst_Fu`](#ldst_fu)
      - [`Branch`](#branch)
      - [`Jump`](#jump)
      - [`ArithmeticSubUnit`](#arithmeticsubunit)
  - [`ArithmeticSubUnit` Class](#arithmeticsubunit-class)
    - [`ArithmeticSubUnitPipeline` Class and the `tick()`  Method](#arithmeticsubunitpipeline-class-and-the-tick--method)
    - [`compute()` Method](#compute-method-3)
    - [`tick()` Method](#tick-method-3)
    - [`single_cycle_compute_tick()` Method](#single_cycle_compute_tick-method)
    - [Implemented Subclasses](#implemented-subclasses-2)
      - [`SUPPORTED_OPS` and `OUTPUT_TYPE`](#supported_ops-and-output_type)
      - [`Alu`](#alu)
      - [`Mul`](#mul)
      - [`Div`](#div)
      - [`Conv`](#conv)
      - [`InvSqrt`](#invsqrt)
      - [`Trig`](#trig)
      - [`Sqrt`](#sqrt)
  - [Configuring the Execute Stage](#configuring-the-execute-stage)
    - [`FunctionalUnitConfig` Class](#functionalunitconfig-class)
    - [`<FunctionalUnitSubclassName>Config` Classes](#functionalunitsubclassnameconfig-classes)
    - [Changing the Number of Units](#changing-the-number-of-units)
    - [Changing the Pipeline Length/Latency of a Unit](#changing-the-pipeline-lengthlatency-of-a-unit)
  - [Creating a New Execution Unit](#creating-a-new-execution-unit)
    - [Create a Class that Inherits `FunctionalSubUnit` or `ArithmeticSubUnit`](#create-a-class-that-inherits-functionalsubunit-or-arithmeticsubunit)
      - [Implement `tick()`](#implement-tick)
      - [Implement `compute()`](#implement-compute)
    - [Add your Class to a `FunctionalUnit` Subclass, or Make a New One](#add-your-class-to-a-functionalunit-subclass-or-make-a-new-one)
    - [Best Practices](#best-practices)
  - [General Notes](#general-notes)


## Overview
The Execute Stage is responsible for performing the computations specified by decode instructions issued by the Issue Stage. It contains all Execution Units necessary for computing the instructions listed in the [Cardinal Instruction Set Architecture](https://docs.google.com/spreadsheets/d/1quvfY0Q_mLP5VfUaNGiiruGoqjCMpCyCKM9KlqbujYM/edit?usp=sharing)

### Terminology
#### Distinguishing between a Functional Unit and Functional Subunit 
There are locations in our code and documentation where "Functional Unit" and "Functional Subunit" are used interchangeably, so I am defining how I will be using the two terms going forward:
- When I use "Functional Unit (FU)", I am referring to a collective group of separate modules that are related to each other.
- In the **current Cx01 architecture**, each FU will contain subunits or "Functional Subunits (FSUs)" which all contain their own pipeline. FSUs will not share any hardware.
- Each FSU will individually communicate with the Issue stage and Writeback stage.
- An FSU may support many types of operations/instructions, or just one type of operation/instruction.

Execution Unit can be used interchangeably for Functional Unit or Functional Subunit depending on the context. However, Execution Unit is *never* used in the code so that this confusion does not appear in the codebase itself.

#### Python/Object-Oriented Programming Terms
- **Method:** A function belonging to a class
- **Member:** A variable belonging to a class
- **Instance:** An instance is the resulting object created when instantiating a class through calling the constructor of that class.
  
#### Python/Object-Oriented Programming Resrouces
- **Pass-by-object-reference:** Read about how Python's programming model works with regard to passing variables and objects to functions and classes [here](https://www.geeksforgeeks.org/python/pass-by-reference-vs-value-in-python/)
  - I highly recommend understanding how this works before tring to write any code in this repo.
- **Inheritance:** Read [this article](https://realpython.com/inheritance-composition-python/) to better understand inheritance, composition and how it can make code better

### Essential Data Structures
#### `Instruction` Class
#### `Bits` Class and the `bitstring` Library

##  `ExecuteStage` Class
> **Note:** If any of this is confusing, try reading the [`FunctionalSubUnit` Class](#functionalsubunit-class) section or the [`FunctionalUnit` Class](#functionalunit-class) section first.

The `ExecuteStage` class wraps all FUs and their methods into one class so that the top-level Python module only needs to import the `ExecuteStage` class and use the methods contained in it for simplicity. It inherits from the `Stage` base class, as do all stages do within the codebase. It contains the following member variables (also known as members):
- **`behind_latch: LatchIF`:** The interface that connects the Issue Stage and Execute Stage
- **`ahead_latches: {'name' : LatchIF}`:** The interfaces that connect the FSUs to the Writeback Stage. Each FSU has their own `LatchIF` instance. The `ExecuteStage` stores all of them, and passes referemces to the `LatchIF` instances to the `FunctionalUnit` subclasses, which then passes references to the `LatchIF` instances to the `FunctionalSubUnit` subclasses. More info on this later in the [`FunctionalSubUnit` Class](#functionalsubunit-class) and [`FunctionalUnit` Class](#functionalunit-class) sections.
- **`functional_units: {'name' : FunctionalUnit}`:** The dictionary that stores instances of all `FunctionalUnit` subclasses
-  **`fust: {'name' : bool}`:** A reference to the Functional Unit Status Table. The FUST is created in the top-level module and then passed by reference
> **Note:** There are more members in this class, but they are either unused or going to be reworked. You likely won't need to know about them. If you have questions about the other members not described, please reach out to Seth McConkey (@s3f2607) on Discord.

### Creating an Instance of the `ExecuteStage` class
The `__init__()` method of the `ExecuteStage` should not be directly called. Instead, `classmethods` should be used. This makes it easier to establish concretes rules with how the `ExecuteStage` class should be set up and gets rid of some of the guesswork that is present when trying to figure out what should be passed to the `__init()__` constructor method.

#### `create_pipeline_stage()` Method
This is a classmethod that should be used for creating an instance of the `ExecuteStage` class by passing a `FunctionalUnitConfig` class instance and the instance of the `fust` from the top-level module. The `FunctionalUnitConfig` class is a dataclass that can be used to configure the `FunctionalUnit` subclasses. More info on this later in the [Configuring the Execute Stage](#configuring-the-execute-stage) section.

Other classmethods can be created that define different configurations if desired. For instance, if you have implemented the sub-core execute stage and want to have a dedicated method of creating that configuration, you can create another classmethod to add alongside `create_pipeline_stage()` called `create_subcore_stage()`. 

### `compute()` Method
The `compute()` method within the `ExecuteStage` class simply iterates through all `FunctionalUnit` instances within the `ExecuteStage.functional_units` member and calls their respective `compute()` methods. These methods typically contain logic for calculating the result of an operation for the instruction in the first stage of the pipeline. More info on `compute()` methods later in the [`FunctionalSubUnit` Class](#functionalsubunit-class) and [`FunctionalUnit` Class](#functionalunit-class) sections.

### `tick()` Method
The `tick()` method acts as positive CLK edge to a flip flop. It is used to move data within FSU pipelines and the stage latches. The `tick()` method within the `ExecuteStage` class accomplishes a few things:

#### 1. Receives the instruction from the Issue Stage
If the target FSU is capable of receiving an instruction, the instruction stored in the `LatchIF` instance is popped from the `LatchIF` instance and then issued to target FSU.

#### 2. Calls the `tick()` methods of the `FunctionalUnit` instances
Each `FunctionalUnit` instance within the `ExecuteStage.functional_units` member dictionary has its `tick()` method called. These `tick()` methods iterate through all the `FunctionalSubUnit` instances stored in the `FunctionalUnit.subunits` member dictionary and calls their `tick()` methods. The `tick()` methods of `FunctionalSubUnit` will be detailed further in the [`FunctionalSubUnit` Class](#functionalsubunit-class) section. But for now, you can think of these `tick()` methods simply acting as a postive CLK edge and advancing instructions through the pipelines of the FSUs.

#### 3. Pushes instructions with completed computations to the Writeback Buffer/Writeback Stage
The `tick()` methods within the `FunctionalSubUnit` instances attempt to push instructions at the end of their pipelines into the Writeback Buffer. Depending on the configuration of the Writeback Buffer, there might be some contention between FSUs, or the buffer might be full. In either of these cases, the instruction may not be pushed to the Writeback Buffer.

> **Note:** The logic within the `tick()` methods are very convoluted and honestly needs some reworking. This team moves quickly and little time is portioned off for refactoring or cleaning up code, unfortunately. In future semesters, I hope more thought is given toward maintaining clean code and writing documentation.

##  `FunctionalUnit` Class
> **Note:** If any of this is confusing, try reading the [`FunctionalSubUnit` Class](#functionalsubunit-class) section first.

The `FunctionalUnit` class groups similar FSUs and wraps all their external-facing methods into one class so that the `ExecuteStage` class only needs to interface with the `FunctionalUnit` subclass instances rather than interfacing with all `FunctionalSubUnit` subclass instances. It contains the following member variables (also known as members):
- **`name: str`:** The identifier of the `FunctionalUnit` instance
- **`subunits: {name : FunctionalSubUnit}`:** A dictionary containing all `FunctionalSubUnit` instances belonging to the FU

###  `compute()` Method
This acts very similarly to the `ExecuteStage` class's `compute()` method. It simply calls all the `compute()` methods of the FSUs in the `FunctionalUnit.subunits` dictionary.
###  `tick()` Method
This also acts very similarly to the `ExecuteStage`. It's purpose is to call all of the `tick()` methods of the FSUs in the `FunctionalUnit.subunits` dictionary. However, it also is in charge of routing the issued instruction to the correct FSU:

1. The `LatchIF` instance that connects the `IssueStage` and `ExecuteStage` classes is passed as a parameter to the `FunctionalUnit.tick()` method.
2. If the target FSU is present in FU, then the instruction is popped from the `LatchIF` instance and passed to the corresponding FSU's `tick()` method for computation. <br> For all FSUs that are not the target of the instruction, `None` is passed to their `tick()` method.
> The `tick()` method of all classes in the Execute Stage is called every cycle, no matter the circumstances. Even if there are no instructions being serviced.

Finally, if there is any output data from the FSUs, it is packaged in a dictionary and returned to the `ExecuteStage` class for storing into the Writeback Buffer.

The `FunctionalUnit.tick()` method is also in charge of updating the FUST. More on this later in the [`FunctionalSubUnit` Class](#functionalsubunit-class) section.

### Implemented Subclasses
> More info on these later. For now, just know that they exist and feel free to take a look at the general logic of each subclass.
#### IntUnit
#### FloatUnit
#### SpecialUnit
#### MemBranchJumpUnit

##  `FunctionalSubUnit` Class
The `FunctionalSubUnit` class is responsible for containing any logic that is common between all FSUs. All FSU implementations **must** inherit from this class. It contains the following member variables (also known as members):
- **`name: str`:** The identifier of the `FunctionalSubUnit` instance
- **`ready_out: bool`:** The signal that is fed back to the Issue Stage Functional Unit Status Table (FUST) to provide backpressure. When this signal is `True`, the `FunctionalUnit` can be issued an instruction and accept. If it is `False`, then its pipeline is full or it is busy and cannot be issued a new instruction.
- **`ex_wb_interface: LatchIF`:** This `LatchIF` instance connects the FSU to the Writeback Buffer. Each FSU gets their own interface to the WritebackBuffer; thus, each `FunctionalSubUnit` instance has its own `LatchIF` instance member.

> **Note:** There are more members in this class, but they are either unused or going to be reworked. You likely won't need to know about them. If you have questions about the other members not described, please reach out to Seth McConkey (@s3f2607) on Discord.

### `compute()` Method
Inside the `compute()` method, logic that should run every cycle but doesn't have to do with moving data forward through the pipeline. For example, an `Alu` subclass of the `FunctionalSubUnit` class would put the actual addition, comparison, shift, and subtraction logic inside of the `compute()` method.

> **Note:** This method was included with arithmetic FSUs (ALU, MUL, DIV, TRIG, etc) in mind. Not all `FunctionalSubUnit` subclasses use this method (like the `Ldst_Fu` subclass) as it isn't totally necessary.

###  `tick()` Method
Again, this method is used as a positive edge CLK signal to any latch/flip-flop like logic in the `FunctionalSubUnit`. All `FunctionalSubUnit` subclasses **must** implement a custom `tick()` method, as the `tick()` method of a `FunctionalSubUnit` is what is called by the `ExecuteStage` and `FunctionalUnit` classes to progress instructions through the pipeline. 

> **Note:** `@abstractmethod` decorators are used to define methods that must be implemented by any concrete subclass. Both `tick()` and `compute()` are abstract methods. However, you may just do this:
> ```
>class MyFunctionalSubUnit(FunctionalSubUnit):
>    def compute():
>        pass
>```
> and that will simply pass over the `compute()` method if there is no logic that needs to be in that method. More info on creating your own `FunctionalSubUnit` subclass implementation later in the [Creating a New Execution Unit](#creating-a-new-execution-unit) section.

### Implemented Subclasses
> More info on these later. For now, just know that they exist and feel free to take a look at the general logic of each subclass.
#### `Ldst_Fu`
#### `Branch`
#### `Jump`
#### `ArithmeticSubUnit`

##  `ArithmeticSubUnit` Class
The `ArithmeticSubUnit` class is a subclass of the `FunctionalSubUnit` class specifically for FSUs that do arithmetic computations (like addition, subtraction, multiplication, trignometric operations, inverse square root, etc). As of now, only units that have fixed latencies and are purely dedicated to generic arithmetic operations should inherit the `ArithmeticSubUnit` class. Units that compute other operations or don't have fixed latency pipelines should inherit from the `FunctionalSubUnit` class instead. Since the `ArithmeticSubUnit` inherits from the `FunctionalSubUnit` class, it contains all methods and members that are present in the `FunctionalSubUnit` class. In addition to these members, it also contains:
- **`latency: int`:** The number of stages in the FSU pipeline/the number of cycles it takes for one instruction to flow through the FSU pipeline
- **`pipeline: ArithmeticSubUnitPipeline`:** The queue-style data structure that acts as a hardware pipeline. It is initalized with `latency - 1` as the size of the queue. `1` must be subtracted from the `latency` parameter since the EX/WB stage `LatchIF` interface that every `FunctionalSubUnit`/`ArithmeticSubUnit` has adds one cycle to the latency.
- **`type_: type`:** Defines the type of data (ie: `int` or `float`) that the `ArithmeticSubUnit` subclass will be operating on. This allows `ArithmeticSubUnit` subclass instances to be initialized for integer or floating-point operations without having to create a whole new subclass.
  
The following members are updated inside of the `ArithmeticSubUnit` constructor/`__init__()` method using the `num` parameter:
- **`name: str`:** The identfier for the `ArithmeticSubUnit` instance. The reason the `name` member must be updated is because if multiple of a single type of `ArithmeticSubUnit` is to be included in the stage, they need an ID number appended to the end (which is the `num` parameter in the `ArithmeticSubUnit` constructor/`__init__()` method) to distinguish them. 
- **`ex_wb_interface: LatchIF`:** Similar to the `name` membe, the name of the `LatchIF` instance must be updated with the new name of the `ArithmeticSubUnit` instance with the ID number `num` appended to it.

>**Note:** This system of identification is pretty clunky as of now. I'm hoping to make a more robust system before the semester ends.

### `ArithmeticSubUnitPipeline` Class and the `tick()`  Method
The `ArithmeticSubUnitPipeline` Class class inherits the `CompactQueue` class, a custom implementation of a queue with some added functionality. It stores `Instruction` class instances, and if there is a NOP/bubble, it stores them as `None` objects. Here is how data flows through an instance of the  `ArithmeticSubUnitPipeline` class via `ArithmeticSubUnit.tick()`:

- New instructions issued to an `ArithmeticSubUnit` instance are placed at the end of the queue
- Each time `ArithmeticSubUnit.tick()` is called, every instruction in the queue is advanced via the `ArithmeticSubUnit.pipeline.advance()` method. This method accepts a new instruction as an argument, which is then placed at the end of the queue. This method also pops whatever is at the beginning of the queue and pushes it to the `ArithmeticSubUnit.ex_wb_interface` if the value is a valid `Instruction` object, if possible. There is some logic within the `ArithmeticSubUnit.tick()` method that makes sure that the Writeback Buffer is ready to accept a new instruction and won't push an instruction to the EX/WB interface latch otherwise.
- If the WritebackBuffer is not ready to accept a new instruction, then the `ArithmeticSubUnit.pipeline.advance()` will not be called. Instead, the `ArithmeticSubUnit.pipeline.compact()` method is called, which also accepts a new instruction as an argument to place at the end of queue. All instructions (except for the one at the beginning of the queue) are moved one place forward in the queue **if** an earlier instruction won't be squashed in this process. The instruction at the beginning of the queue can't be pushed to `ArithmeticSubUnit.ex_wb_interface` in this scenario, so it is not popped and stays at the beginning of the queue. 
- In the case that an `ArithmeticSubUnit` instance's pipeline/queue is full AND the WritebackBuffer can't receive a new instruction, there is no movement in the pipeline/queue. Additionally, the `ready_out` signal to the FUST is set to `False` to signify that a new instruction cannot be issued.
  
### `compute()` Method
In real hardware, the computation of an operation takes place in multiple steps in each stage of that execution unit's pipeline. However, in order to simplify computations while staying true to the cycle-level timing of hardware, the `compute()` method of `ArithmeticSubUnit` instances fully compute the operation on the first cycle it is present in the `ArithmeticSubUnitPipeline` instance. 

### `tick()` Method
A lot of the detail of the `ArithmeticSubUnit.tick()` method is described in the [`ArithmeticSubUnitPipeline` Class and the `tick()`  Method](#arithmeticsubunitpipeline-class-and-the-tick--method) section above. The high-level overview of this method is simply addressing backpressure from the Writeback Buffer, advancing Instructions in the pipeline, and asserting backpressure to the Issue Stage via the `ready_out` signal to the FUST.

### `single_cycle_compute_tick()` Method
This is where things get wonky. `ArithmeticSubUnit` instances with only single cycle require an extra call to the `ArithmeticSubUnit.pipeline.advance()` method. This is necessary because the `ArithmeticSubUnitPipeline` queue must have a minimum size of 1. I mentioned previously that the `LatchIF` between the Execute Stage and Writeback Stage adds a cycle of latency to the pipeline. Therefore, a single-cycle latency `ArithmeticSubUnit` instance is simulated as having a 2-stage pipeline (1 stage from the queue, 1 stage from the `LatchIF`), but instructions are advanced twice per cycle to account for this, which results in a single-cycle latency pipeline. You don't need to understand how this works or why it's needed; the only takeaway you need is that **all `ArithmeticSubUnit.tick()` methods require this block of code at the end of them:**

```
if self.latency == 1:
    self.single_cycle_latency_compute_tick()
```

### Implemented Subclasses
> More info on these later. For now, just know that they exist and feel free to take a look at the general logic of each subclass.

#### `SUPPORTED_OPS` and `OUTPUT_TYPE` 
The `SUPPORTED_OPS` member is added above the constructor/`__init()__` method of each `ArithmeticSubUnit` subclass. It defines the supported `int` type operations and `float` type operations. If an operation is passed to the `ArithmeticSubUnit` and it isn't present in the `SUPPORTED_OPS` list for the configured `type`, then the subclass will throw an error.
Additionally, some (very few, I think just `Alu`) subclasses require a definition for the output type of the operations in `SUPPORTED_OPS`. For instance, the comaprison operation `R_Op.SLTF` (Set Less Than Float) compares two float operands, and outputs an integer result of `1` or `0`. In this situation, the source operands and result have different types, so this is reflected in the `OUTPUT_TYPE` member (also placed about the `__init__` method).

#### `Alu`
#### `Mul`
#### `Div`
#### `Conv`
#### `InvSqrt`
#### `Trig`
#### `Sqrt`

## Configuring the Execute Stage
Throughout the Execute Stage, configuration classes are used to define parameters of classes. This is good practice for a few reasons:
- Gets rid of "magic numbers" and replaces them with labelled arguments/values
- Allows for the validation of arguments/values passed to parameters
- Makes it easy to define many configurations and switch between them
- Allows for a configuration file to be used, which is a must when running performance studies that compare the results of many different configurations

The Execute Stage features a hierarchy of nested configuration classes.

### `FunctionalUnitConfig` Class
The `FunctionalUnitConfig` class contains instances of configuration classes for all `FunctionalUnit` subclasses. This means that every `FunctionalUnit` subclass must have a configuration class created alongside it. An instance of the `FunctionalUnitConfig` class is passed to the `ExecuteStage.create_pipeline_stage()` class method to configure what FUs are included in the Execute Stage.

### `<FunctionalUnitSubclassName>Config` Classes
As mentioned before, there is a corresponding configuration class for each `FunctionalUnit` subclass. 
> **An example of the naming convention for one these configuration classes:** the `FunctionalUnit` subclass containing all of the integer FSUs is called `IntUnit`. The corresponding configuration class is called `IntUnitConfig`.

### Changing the Number of Units
### Changing the Pipeline Length/Latency of a Unit

## Creating a New Execution Unit
### Create a Class that Inherits `FunctionalSubUnit` or `ArithmeticSubUnit`
#### Implement `tick()`
#### Implement `compute()`
### Add your Class to a `FunctionalUnit` Subclass, or Make a New One
### Best Practices

## General Notes



