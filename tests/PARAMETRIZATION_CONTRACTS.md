# Test Parametrization Contracts

This document defines canonical parametrization patterns for the pytest suite. These conventions ensure consistent semantics across tests and prevent ad-hoc duplication.

---

## frame_analyzer: Frame Count Parametrization `[1, 3, 5]`

**Location**: `tests/test_frame_analyzer.py::TestAnalyzeFrameSequence::test_analyze_frame_sequence_deterministic`

**Parametrization**: `@pytest.mark.parametrize("num_frames", [1, 3, 5])`

### Contract

The frame_analyzer module parametrizes tests across **[1, 3, 5] frame counts** to:

1. **num_frames=1** (Single Frame)
   - **Purpose**: Boundary case validation — tests the analyzer's behavior with minimal input
   - **What it validates**: Edge case handling, single-frame indexing, no sequence analysis bias
   - **Why it matters**: Catches off-by-one errors in frame iteration and ensures graceful handling of minimal workloads

2. **num_frames=3** (Small Batch)
   - **Purpose**: ThreadPoolExecutor parallelization stress test with small overhead
   - **What it validates**: Determinism under parallel loading, race condition absence with minimal synchronization overhead
   - **Why it matters**: Verifies that parallel execution doesn't introduce non-determinism; catches subtle race conditions missed by sequential execution

3. **num_frames=5** (Medium Batch)
   - **Purpose**: Realistic workload validation — typical playtest frame capture size
   - **What it validates**: Correct behavior at "normal" workload; statistical aggregation correctness (histograms, differences)
   - **Why it matters**: Ensures the analyzer produces correct frame difference metrics and histogram stats at realistic scales

### Rationale

The [1, 3, 5] matrix ensures:
- **Single source of truth**: Frame count parametrization is consolidated in this test
- **No ad-hoc duplication**: Future frame-count tests should reuse or extend this test, not duplicate parametrization
- **Clear semantics**: Each size has explicit intent (boundary, parallelization, realistic load)
- **Xdist-compatible**: Parametrization shards well across pytest-xdist workers

### Adding New Frame-Count Tests

**DO**: 
- If testing `analyze_frame_sequence()` determinism → extend/reuse `test_analyze_frame_sequence_deterministic`
- Reference this contract in new test docstrings: `# See: tests/PARAMETRIZATION_CONTRACTS.md (frame_analyzer)`

**DON'T**:
- Add frame-count parametrization in other tests without documenting why (e.g., `@pytest.mark.parametrize("n", [2, 4, 6])` ad-hoc)
- Extend [1, 3, 5] to [1, 2, 3, 4, 5, ...] without discussing the intent

---

## Other Notable Parametrization Patterns

### test_map_format: Level Iteration (`_ALL_LEVELS`)

**Location**: `tests/test_map_format.py`

**Parametrization**: `@pytest.mark.parametrize("episode,level", _ALL_LEVELS)`

**Purpose**: Load all episode/level combinations (E1–E4, each with L1–L8 levels). Tests format parsing and geometry validation across the entire level set.

**Pattern**: Tuple-based parametrization for cross-product coverage (16 levels total).

---

### test_audio_pipeline: Audio File Validation

**Location**: `tests/test_audio_pipeline.py`, `tests/test_generate_audio.py`

**Parametrization**: `@pytest.mark.parametrize("filename,expected_voice", [...])`

**Purpose**: Validate audio generation across multiple output files with expected voice assignments.

**Pattern**: Multi-parameter tuple for paired validation (file → voice matching).

---

### test_engine_bounds_hardening: Exception Type Coverage

**Location**: `tests/test_engine_bounds_hardening.py`

**Parametrization**: `@pytest.mark.parametrize("exception_type,exception_args", [...])`

**Purpose**: Verify bounds checks raise correct exceptions for various invalid inputs.

**Pattern**: Exception class + constructor args for comprehensive error path coverage.

---

## Guidelines for Adding Parametrization

1. **Define intent clearly**: Document WHY each parameter value is included
2. **Use symbolic names**: Prefer `_ALL_LEVELS` over inline lists for maintainability
3. **Consolidate related tests**: Don't scatter parametrization across multiple tests with overlapping intent
4. **Reference this contract**: Add a comment in new parametrized tests pointing here
5. **Consider xdist compatibility**: Ensure parametrization shards well with `pytest-xdist` (avoid massive parameter sets without chunking)

---

## References

- **Module docstring**: `tools/frame_analyzer.py` — contains test execution notes
- **Test convention**: `tests/conftest.py:19-37` — Frame Analyzer Test Contract definition
- **Main test**: `tests/test_frame_analyzer.py:327–356` — `test_analyze_frame_sequence_deterministic`
