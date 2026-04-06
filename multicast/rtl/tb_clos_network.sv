// tb_clos_network.sv
// Functional testbench for the 3-stage Clos network top level.
//
// Tests (mirrors test_clos.py):
//   [A] Unicast     — every bank to every thread (1024 combinations)
//   [B] Multicast   — representative destination-mask patterns
//   [C] Broadcast   — every bank to all 32 threads
//   [D] Errors      — access-violation and unmapped flits routed correctly
//   [E] Simultaneous — all 32 banks fire unicast flits in the same cycle
//
// Scoreboard uses per-thread dynamic queues of expected {data, error} pairs.
// The thread monitor pops and compares on every valid+ready handshake.
//
// Compile + run example (Questa / ModelSim):
//   vlog -sv rtl/clos_pkg.sv rtl/ingress_switch.sv rtl/middle_switch.sv \
//             rtl/egress_switch.sv rtl/mshr_table.sv rtl/clos_network.sv \
//             rtl/tb_clos_network.sv
//   vsim -c tb_clos_network -do "run -all; quit"
//
// VCS example:
//   vcs -sverilog -timescale=1ns/1ps \
//       rtl/clos_pkg.sv rtl/ingress_switch.sv rtl/middle_switch.sv \
//       rtl/egress_switch.sv rtl/mshr_table.sv rtl/clos_network.sv \
//       rtl/tb_clos_network.sv -o simv && ./simv
//
// Verilator (lint/compile check only — no timing):
//   verilator --lint-only --sv rtl/clos_pkg.sv ... rtl/tb_clos_network.sv

`timescale 1ns/1ps

import clos_pkg::*;

module tb_clos_network;

  // -------------------------------------------------------------------------
  // Error-code aliases (match clos_network_sim.py)
  // -------------------------------------------------------------------------
  localparam logic [ERR_W-1:0] ERR_GOOD     = 2'b00;
  localparam logic [ERR_W-1:0] ERR_ACCESS   = 2'b01;
  localparam logic [ERR_W-1:0] ERR_ECC      = 2'b10;
  localparam logic [ERR_W-1:0] ERR_UNMAPPED = 2'b11;

  // -------------------------------------------------------------------------
  // Clock — 100 MHz (10 ns period)
  // -------------------------------------------------------------------------
  logic clk = 1'b0;
  always #5 clk = ~clk;

  // -------------------------------------------------------------------------
  // DUT ports
  // -------------------------------------------------------------------------
  logic  rst_n;

  logic  bank_valid [NUM_BANKS];
  logic  bank_ready [NUM_BANKS];
  flit_t bank_flit  [NUM_BANKS];

  logic                      thread_valid [NUM_THREADS];
  logic                      thread_ready [NUM_THREADS];
  logic [THREAD_FLIT_W-1:0]  thread_flit  [NUM_THREADS];

  // -------------------------------------------------------------------------
  // DUT instantiation
  // -------------------------------------------------------------------------
  clos_network dut (
    .clk          (clk),
    .rst_n        (rst_n),
    .bank_valid   (bank_valid),
    .bank_ready   (bank_ready),
    .bank_flit    (bank_flit),
    .thread_valid (thread_valid),
    .thread_ready (thread_ready),
    .thread_flit  (thread_flit)
  );

  // -------------------------------------------------------------------------
  // Scoreboard
  // -------------------------------------------------------------------------
  typedef struct {
    logic [DATA_W-1:0] data;
    logic [ERR_W-1:0]  error;
  } exp_t;

  exp_t  exp_q [NUM_THREADS][$];   // expected-delivery queues, one per thread
  int    total_pass = 0;
  int    total_fail = 0;
  string fail_msgs[$];

  // Thread monitor — runs throughout simulation.
  // Samples one cycle after posedge to avoid race with DUT outputs.
  initial begin
    forever begin
      @(posedge clk); #1;
      for (int t = 0; t < NUM_THREADS; t++) begin
        if (thread_valid[t] && thread_ready[t]) begin
          // thread_flit[t] = flit[38:0]
          //   data  at [38:7]  (THREAD_FLIT_W-1 downto ERR_W+5 = 38 downto 7)
          //   error at [ 1:0]  (ERR_W-1        downto 0        =  1 downto 0)
          automatic logic [DATA_W-1:0] rx_data  = thread_flit[t][THREAD_FLIT_W-1 : ERR_W+5];
          automatic logic [ERR_W-1:0]  rx_err   = thread_flit[t][ERR_W-1:0];

          if (exp_q[t].size() == 0) begin
            $display("  FAIL: thread%0d received UNEXPECTED flit  data=0x%08X err=%02b",
                     t, rx_data, rx_err);
            total_fail++;
            fail_msgs.push_back($sformatf(
              "thread%0d unexpected flit data=0x%08X err=%02b", t, rx_data, rx_err));
          end else begin
            automatic exp_t e = exp_q[t].pop_front();
            if (rx_data === e.data && rx_err === e.error) begin
              total_pass++;
            end else begin
              $display("  FAIL: thread%0d  got data=0x%08X err=%02b  exp data=0x%08X err=%02b",
                       t, rx_data, rx_err, e.data, e.error);
              total_fail++;
              fail_msgs.push_back($sformatf(
                "thread%0d: got 0x%08X/%02b  exp 0x%08X/%02b",
                t, rx_data, rx_err, e.data, e.error));
            end
          end
        end
      end
    end
  end

  // -------------------------------------------------------------------------
  // Utility: all threads always accept (thread_ready = 1)
  // Override per-thread after reset if back-pressure tests are needed.
  // -------------------------------------------------------------------------
  initial begin
    for (int t = 0; t < NUM_THREADS; t++)
      thread_ready[t] = 1'b1;
  end

  // -------------------------------------------------------------------------
  // Helper: build a flit_t
  // -------------------------------------------------------------------------
  function automatic flit_t make_flit(
    input logic [NUM_THREADS-1:0] dest_mask,
    input logic [DATA_W-1:0]      data,
    input logic [ERR_W-1:0]       error = ERR_GOOD
  );
    flit_t f;
    f.dest_mask = dest_mask;
    f.data      = data;
    f.reserved  = '0;
    f.error     = error;
    return f;
  endfunction

  // -------------------------------------------------------------------------
  // Helper: enqueue expected deliveries for every set bit in dest_mask
  // -------------------------------------------------------------------------
  task automatic expect_flit(
    input logic [NUM_THREADS-1:0] dest_mask,
    input logic [DATA_W-1:0]      data,
    input logic [ERR_W-1:0]       error = ERR_GOOD
  );
    for (int t = 0; t < NUM_THREADS; t++) begin
      if (dest_mask[t]) begin
        automatic exp_t e;
        e.data  = data;
        e.error = error;
        exp_q[t].push_back(e);
      end
    end
  endtask

  // -------------------------------------------------------------------------
  // Helper: send one flit from a single bank, respecting back-pressure.
  //
  // Protocol (valid/ready):
  //   - Assert valid+flit after a posedge (seen by DUT on the next posedge).
  //   - Hold until bank_ready is high at a posedge (handshake complete).
  //   - Deassert valid one cycle later.
  // -------------------------------------------------------------------------
  task automatic send_flit(input int bank_id, input flit_t f);
    // Drive after a falling edge so setup time is met before the next posedge.
    @(negedge clk);
    bank_valid[bank_id] = 1'b1;
    bank_flit[bank_id]  = f;
    // Wait for the DUT to assert ready (handshake at posedge).
    @(posedge clk);
    while (!bank_ready[bank_id]) @(posedge clk);
    // Hold valid one more half-cycle then deassert.
    @(negedge clk);
    bank_valid[bank_id] = 1'b0;
  endtask

  // -------------------------------------------------------------------------
  // Helper: wait until all expected queues drain (or declare timeout).
  // -------------------------------------------------------------------------
  task automatic drain(input int timeout_cycles = 300);
    for (int cyc = 0; cyc < timeout_cycles; cyc++) begin
      automatic int pending = 0;
      for (int t = 0; t < NUM_THREADS; t++) pending += int'(exp_q[t].size());
      if (pending == 0) return;
      @(posedge clk);
    end
    // Timeout — report every undelivered expectation.
    for (int t = 0; t < NUM_THREADS; t++) begin
      while (exp_q[t].size() > 0) begin
        automatic exp_t e = exp_q[t].pop_front();
        $display("  FAIL: thread%0d TIMEOUT — expected data=0x%08X err=%02b never arrived",
                 t, e.data, e.error);
        total_fail++;
        fail_msgs.push_back($sformatf(
          "thread%0d timeout: data=0x%08X err=%02b", t, e.data, e.error));
      end
    end
  endtask

  // -------------------------------------------------------------------------
  // Helper: reset sequence
  // -------------------------------------------------------------------------
  task do_reset();
    rst_n = 1'b0;
    for (int b = 0; b < NUM_BANKS; b++) begin
      bank_valid[b] = 1'b0;
      bank_flit[b]  = '0;
    end
    repeat(4) @(posedge clk);
    rst_n = 1'b1;
    repeat(2) @(posedge clk);
  endtask

  // ==========================================================================
  // Test A: Unicast — every bank to every thread
  // ==========================================================================
  task test_A_unicast();
    $display("\n============================================================");
    $display("[A] UNICAST — every bank to every thread  (1024 combinations)");
    $display("============================================================");

    for (int b = 0; b < NUM_BANKS; b++) begin
      for (int t = 0; t < NUM_THREADS; t++) begin
        automatic logic [DATA_W-1:0]      dv   = (b << 8) | t;
        automatic logic [NUM_THREADS-1:0] mask = NUM_THREADS'(1) << t;
        expect_flit(mask, dv);
        send_flit(b, make_flit(mask, dv));
        drain(100);
      end
    end

    $display("  Done: 1024 unicast combinations");
  endtask

  // ==========================================================================
  // Test B: Multicast — representative destination patterns
  // ==========================================================================
  task test_B_multicast();
    $display("\n============================================================");
    $display("[B] MULTICAST — representative destination patterns");
    $display("============================================================");

    // Each case: {bank, dest_mask, description}
    // Matching test_clos.py MULTICAST_PATTERNS.
    begin
      automatic int b;
      automatic logic [31:0] m;
      automatic logic [31:0] dv;
      automatic int          nc;  // number of destinations

      // two threads, same egress group (threads 0,1)
      b=0; m=32'h0000_0003; nc=$countones(m);
      dv=32'hAB000000|(b<<8)|nc; expect_flit(m,dv); send_flit(b,make_flit(m,dv)); drain(100);
      $display("  PASS (pending check): bank%0d -> [%0d] two threads same egress group", b, nc);

      // two threads, different egress groups (threads 0, 8)
      b=1; m=32'h0000_0101; nc=$countones(m);
      dv=32'hAB000000|(b<<8)|nc; expect_flit(m,dv); send_flit(b,make_flit(m,dv)); drain(100);
      $display("  PASS (pending check): bank%0d -> [%0d] two threads different egress groups", b, nc);

      // four threads, one per egress group (threads 0,8,16,24)
      b=2; m=32'h0101_0101; nc=$countones(m);
      dv=32'hAB000000|(b<<8)|nc; expect_flit(m,dv); send_flit(b,make_flit(m,dv)); drain(100);
      $display("  PASS (pending check): bank%0d -> [%0d] four threads across 4 egress groups", b, nc);

      // eight threads, one per egress (threads 0,4,8,12,16,20,24,28)
      b=3; m=32'h1111_1111; nc=$countones(m);
      dv=32'hAB000000|(b<<8)|nc; expect_flit(m,dv); send_flit(b,make_flit(m,dv)); drain(100);
      $display("  PASS (pending check): bank%0d -> [%0d] eight threads one per egress", b, nc);

      // threads 0,1,4,8,20,31 — mixed groups
      b=5; m=32'h8010_0113; nc=$countones(m);
      dv=32'hAB000000|(b<<8)|nc; expect_flit(m,dv); send_flit(b,make_flit(m,dv)); drain(100);
      $display("  PASS (pending check): bank%0d -> [%0d] threads 0,1,4,8,20,31 mixed", b, nc);

      // all threads in egress group 0 (threads 0-3)
      b=10; m=32'h0000_000F; nc=$countones(m);
      dv=32'hAB000000|(b<<8)|nc; expect_flit(m,dv); send_flit(b,make_flit(m,dv)); drain(100);
      $display("  PASS (pending check): bank%0d -> [%0d] all threads egress 0 (0-3)", b, nc);

      // all threads in egress group 7 (threads 28-31)
      b=15; m=32'hF000_0000; nc=$countones(m);
      dv=32'hAB000000|(b<<8)|nc; expect_flit(m,dv); send_flit(b,make_flit(m,dv)); drain(100);
      $display("  PASS (pending check): bank%0d -> [%0d] all threads egress 7 (28-31)", b, nc);

      // half the threads — even (0,2,4,...,30)
      b=20; m=32'h5555_5555; nc=$countones(m);
      dv=32'hAB000000|(b<<8)|nc; expect_flit(m,dv); send_flit(b,make_flit(m,dv)); drain(150);
      $display("  PASS (pending check): bank%0d -> [%0d] half threads (even)", b, nc);

      // half the threads — odd (1,3,5,...,31)
      b=25; m=32'hAAAA_AAAA; nc=$countones(m);
      dv=32'hAB000000|(b<<8)|nc; expect_flit(m,dv); send_flit(b,make_flit(m,dv)); drain(150);
      $display("  PASS (pending check): bank%0d -> [%0d] half threads (odd)", b, nc);

      // 31 threads — all except thread 0
      b=31; m=32'hFFFF_FFFE; nc=$countones(m);
      dv=32'hAB000000|(b<<8)|nc; expect_flit(m,dv); send_flit(b,make_flit(m,dv)); drain(200);
      $display("  PASS (pending check): bank%0d -> [%0d] all threads except thread 0", b, nc);
    end
  endtask

  // ==========================================================================
  // Test C: Broadcast — every bank to all 32 threads
  // ==========================================================================
  task test_C_broadcast();
    logic [NUM_THREADS-1:0] all_mask = '1;

    $display("\n============================================================");
    $display("[C] BROADCAST — every bank to all 32 threads");
    $display("============================================================");

    for (int b = 0; b < NUM_BANKS; b++) begin
      automatic logic [DATA_W-1:0] dv = 32'hBC000000 | b;
      expect_flit(all_mask, dv);
      send_flit(b, make_flit(all_mask, dv));
      drain(300);
    end

    $display("  Done: 32 broadcasts");
  endtask

  // ==========================================================================
  // Test D: Error propagation
  // ==========================================================================
  task test_D_errors();
    $display("\n============================================================");
    $display("[D] ERROR PROPAGATION — error flits routed to correct thread");
    $display("============================================================");

    begin
      automatic flit_t       f;
      automatic logic [31:0] m;

      // ERR_UNMAPPED: bank 0 -> thread 0
      m=32'h0000_0001; f=make_flit(m,32'h0,ERR_UNMAPPED);
      expect_flit(m,32'h0,ERR_UNMAPPED); send_flit(0,f); drain(100);
      $display("  UNMAPPED  bank0  -> thread0");

      // ERR_UNMAPPED: bank 7 -> thread 15
      m=32'h0000_8000; f=make_flit(m,32'h0,ERR_UNMAPPED);
      expect_flit(m,32'h0,ERR_UNMAPPED); send_flit(7,f); drain(100);
      $display("  UNMAPPED  bank7  -> thread15");

      // ERR_UNMAPPED: bank 15 -> thread 31
      m=32'h8000_0000; f=make_flit(m,32'h0,ERR_UNMAPPED);
      expect_flit(m,32'h0,ERR_UNMAPPED); send_flit(15,f); drain(100);
      $display("  UNMAPPED  bank15 -> thread31");

      // ERR_ACCESS: bank 0 -> thread 7
      m=32'h0000_0080; f=make_flit(m,32'h0,ERR_ACCESS);
      expect_flit(m,32'h0,ERR_ACCESS); send_flit(0,f); drain(100);
      $display("  ACCESS    bank0  -> thread7");

      // ERR_ACCESS: bank 31 -> thread 24
      m=32'h0100_0000; f=make_flit(m,32'h0,ERR_ACCESS);
      expect_flit(m,32'h0,ERR_ACCESS); send_flit(31,f); drain(100);
      $display("  ACCESS    bank31 -> thread24");
    end
  endtask

  // ==========================================================================
  // Test E: Simultaneous — all 32 banks assert valid in the same cycle
  // ==========================================================================
  task test_E_simultaneous();
    $display("\n============================================================");
    $display("[E] SIMULTANEOUS — all 32 banks fire unicast flits at once");
    $display("============================================================");

    // Each bank b targets thread b.
    for (int b = 0; b < NUM_BANKS; b++) begin
      automatic logic [DATA_W-1:0]      dv   = 32'hCC000000 | b;
      automatic logic [NUM_THREADS-1:0] mask = NUM_THREADS'(1) << b;
      expect_flit(mask, dv);
      bank_flit[b]  = make_flit(mask, dv);
      bank_valid[b] = 1'b1;
    end

    // Deassert each bank as soon as its handshake completes.
    begin
      automatic int remaining = NUM_BANKS;
      while (remaining > 0) begin
        @(posedge clk); #1;
        for (int b = 0; b < NUM_BANKS; b++) begin
          if (bank_valid[b] && bank_ready[b]) begin
            bank_valid[b] = 1'b0;
            remaining--;
          end
        end
      end
    end

    drain(500);
    $display("  Done: 32 concurrent unicast sends");
  endtask

  // ==========================================================================
  // Main
  // ==========================================================================
  initial begin
    // Optional: dump waveforms (comment out if not needed)
    $dumpfile("tb_clos_network.vcd");
    $dumpvars(0, tb_clos_network);

    $display("============================================================");
    $display("Clos Network — RTL Functional Testbench");
    $display("============================================================");

    do_reset();

    test_A_unicast();
    test_B_multicast();
    test_C_broadcast();
    test_D_errors();
    test_E_simultaneous();

    // Let the monitor flush any in-flight flits.
    repeat(20) @(posedge clk);

    // Final report
    $display("\n============================================================");
    if (total_fail == 0 && fail_msgs.size() == 0) begin
      $display("RESULT: ALL TESTS PASSED  (%0d checks)", total_pass);
    end else begin
      $display("RESULT: %0d FAILURE(S)  /  %0d PASSED", total_fail, total_pass);
      foreach (fail_msgs[i]) $display("  - %s", fail_msgs[i]);
    end
    $display("============================================================");

    $finish;
  end

  // ==========================================================================
  // Watchdog — abort if simulation runs away
  // ==========================================================================
  initial begin
    #5_000_000;
    $display("FATAL: simulation timeout at %0t — check for deadlock", $time);
    $finish;
  end

endmodule : tb_clos_network
