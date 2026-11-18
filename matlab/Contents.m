% Multiplex-NBS toolbox for MATLAB
% Version 0.1.0  18-Nov-2026
%
% Network-based statistics for one network or a stack of networks measured
% at successive time points, frequency bins or other ordered layers.
% Add this folder to the path:  addpath('multiplex-nbs/matlab')
%
% Analysis
%   mnbs_analyze        - Multiplex-NBS / Layer-wise NBS with permutation inference.
%   mnbs_gui            - Interactive MATLAB interface.
%
% Data
%   mnbs_load_demo      - Bundled practice datasets (shared with Python and the app).
%   mnbs_demo           - Generate a small synthetic dataset.
%
% Building blocks (for custom pipelines)
%   mnbs_edgestat_group - Edge-by-layer Welch or paired t statistics.
%   mnbs_edgestat_glm   - Edge-by-layer GLM t or F statistics.
%   mnbs_components     - Connected components of region-layer sites.
%   mnbs_permute        - Permutation null, two-sample and paired designs.
%   mnbs_permute_glm    - Permutation null, general linear model.
%   mnbs_summarize      - Corrected p-values and a component summary.
%   mnbs_tcdf           - Student-t CDF without the Statistics Toolbox.
%
% Testing
%   mnbs_selftest       - Regression checks shared with the Python package.
%
% Examples: see ../examples/matlab. Documentation: ../docs/matlab-api.md.
% Classic NBS on a single network is provided by the Python package and the
% desktop app. The original March 2026 prototype is kept in legacy/ for
% provenance; do not add legacy/ to the path.
%
% Ismail MM, Williamson BJ, Kadis DS. GNU General Public License v3 or later.
% https://github.com/Minarose/multiplex-nbs
