# Classic NBS and Multiplex-NBS

Select **Classic NBS** to test connected edges in one undirected network per observation. Select **Multiplex-NBS** to test components of node–layer sites across an ordered axis. Both modes repeat the edge tests, thresholding, and component search for every permutation and compare each observed component to the largest permuted component statistic. The component carries the corrected p-value. [Original NBS paper](https://doi.org/10.1016/j.neuroimage.2010.06.041)

| Setting | Classic NBS | Multiplex-NBS |
|---|---|---|
| Inference domain | One matrix per observation, or one prespecified slice of a stack | All supplied layers |
| Connections | Retained edges join their endpoints | Retained edges join endpoints within a layer. With consecutive adjacency, shared active nodes join neighboring layers |
| Extent | Count of retained undirected edges | Count of distinct node–layer sites |
| Weighted statistic | Mass sums the full tail-adjusted retained edge statistics; intensity sums each minus the primary threshold | The same two choices, over the component's retained edges in every layer |
| Correction | Largest component within the selected matrix, across requested tails | Largest component across layers and requested tails |
| Result index | The analyzed slice has local index 1. The report includes its original layer number and axis value | Layer indices follow the input stack |

The Classic NBS implementation follows the extent definition in the original method and the intensity calculation in the NBS Connectome v1.2 release. Section 2.5 of the manual describes intensity using a sum of statistics, while the released NBSstats.m subtracts the primary threshold from each retained statistic for both observed and permuted components. This app uses the released calculation. For example, two connected edges with t values of 4 and 5 at threshold 3 have extent 2 and intensity 3. [NBS v1.2 reference manual](https://www.nitrc.org/frs/download.php/5331/Reference_Manual_NBS_v1.2.pdf) · [Official release files](https://www.nitrc.org/frs/?group_id=629&release_id=2125) · [Developer discussion](https://www.nitrc.org/forum/message.php?msg_id=39599)

## Inputs and outputs

Python accepts classic input shaped observations × nodes × nodes. Numeric MATLAB W uses nodes × nodes × observations, or a cell per observation. For a layered dataset set the one-based input layer explicitly before inspecting results.

```sh
multiplex-nbs run data.npz --method classic --layer 3 --metric extent --output classic.json
```

A single-layer input defaults to layer 1. In Python use `classic_nbs(data, layer=3, metric="intensity")`; in MATLAB, classic NBS is available through the original NBS Connectome toolbox. Every method accepts `extent`, `mass` or `intensity`. In the apps, intensity is chosen by selecting Mass and ticking **Subtract the threshold from each edge**.

CSV files identify inference mode, extent unit, mass, intensity, tested metric, and, for Classic NBS, the original input layer. JSON/MAT retain the full statistic map, positive or negative component membership, threshold, null maxima, and analysis settings. Raw statistic mass remains available as a descriptive quantity.

## Reference check

We used the matrices.mat and designMatrix.txt files in the official v1.2 SchizophreniaExample as an external verification dataset. With the supplied design, GLM contrast [-1, 1], and right-tailed strict threshold t > 3.1, the implementation found one observed component with 40 edges and 29 nodes. Its intensity was 11.5400132708. A separate calculation using SciPy's pooled two-sample t test and a breadth-first traversal agreed on all three quantities. With the opposite contrast, zero edges survived the threshold. The reference data and original MATLAB toolbox are external to the app. [Official example archive](https://www.nitrc.org/frs/download.php/5064/NBS1.2.zip)

Automated tests check numerical permutation maxima on a three-node graph for both extent and intensity, separate signed components, an edge exactly at the threshold, and equivalence of extracting a chosen slice and supplying it as a single matrix. The released MATLAB program itself was not run in these comparisons.

## Scope of compatibility

Classic and multiplex use this app's design and resampling engine. An independent group analysis uses Welch t. A supplied group-indicator design and GLM contrast provide the pooled OLS t used in the official group example. Paired comparisons use sign flips of whole within-participant differences. A one-sample design applies a random sign to each independent observation’s full network. Under the null, each signed map must have the same distribution after reversal. Classic uses the arithmetic mean in input connectivity units, following the calculation in NBSglm.m. Multiplex uses a studentized one-sample t statistic. Both require signed inputs and disallow the absolute-value transformation. The one-sample option uses every observation, independently of group labels or a loaded GLM. GLM t/F contrasts support residual or row permutations and exchangeability blocks. Positive and negative signed components are built separately in a two-sided test with a shared permutation maximum.

For B random permutations, this app reports (1 + exceedances)/(B + 1) and includes components with p ≤ the reporting cutoff. The v1.2 MATLAB source uses exceedances/B and the same inclusive reporting cutoff. Matching a reference analysis requires matching the design, contrast, threshold, tail, measure, permutation procedure, and reporting convention.

The bundled Classic NBS mode covers undirected component inference in the desktop app, Python API, and CLI. The original NBS Connectome provides additional utilities including edgewise FDR and its MATLAB session/viewer formats. Its separate directed-network module also remains available from the original project. The native multiplex MATLAB toolbox in this repository retains its existing node–layer analyses. [Original NBS Connectome project](https://www.nitrc.org/projects/nbs/)
