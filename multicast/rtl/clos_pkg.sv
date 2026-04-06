// clos_pkg.sv
// Package containing all parameters and type definitions for the Clos network.

package clos_pkg;

  // ---------------------------------------------------------------------------
  // Flit field widths
  // ---------------------------------------------------------------------------
  parameter int unsigned FLIT_W   = 71;   // total flit width [70:0]
  parameter int unsigned DEST_W   = 32;   // destination bitmask width [70:39]
  parameter int unsigned DATA_W   = 32;   // read-data width [38:7]
  parameter int unsigned ERR_W    = 2;    // error-code width [1:0]

  // ---------------------------------------------------------------------------
  // Network sizing
  // ---------------------------------------------------------------------------
  parameter int unsigned NUM_BANKS          = 32;
  parameter int unsigned NUM_THREADS        = 32;
  parameter int unsigned NUM_INGRESS        = 8;
  parameter int unsigned NUM_MIDDLE         = 8;
  parameter int unsigned NUM_EGRESS         = 8;
  parameter int unsigned BANKS_PER_INGRESS  = 4;   // inputs  per ingress switch
  parameter int unsigned THREADS_PER_EGRESS = 4;   // outputs per egress  switch

  // ---------------------------------------------------------------------------
  // Flit layout
  //   [70:39] dest_mask  (DEST_W  = 32 bits)
  //   [38: 7] data       (DATA_W  = 32 bits)
  //   [ 6: 2] reserved   (5 bits)
  //   [ 1: 0] error      (ERR_W   =  2 bits)
  // ---------------------------------------------------------------------------
  typedef struct packed {
    logic [DEST_W-1:0] dest_mask;   // [70:39]
    logic [DATA_W-1:0] data;        // [38: 7]
    logic [4:0]        reserved;    // [ 6: 2]
    logic [ERR_W-1:0]  error;       // [ 1: 0]
  } flit_t;                         // 71 bits total

  // Egress output to threads: dest field stripped → [38:0]
  // {data[31:0], error[1:0]} packed as [38:0]
  // data occupies [38:7] and error occupies [1:0] in the original flit,
  // so the thread-facing word is just flit[38:0].
  parameter int unsigned THREAD_FLIT_W = 39;  // DATA_W + 5(reserved) + ERR_W

endpackage : clos_pkg
