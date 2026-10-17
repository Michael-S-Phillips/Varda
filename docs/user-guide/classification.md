# Classification

**Processing → Classification** makes class maps from an image. Five
classifiers learn from ROIs you draw (supervised); **K-Means Clustering**
needs none (unsupervised). The same menu has the class map tools (Density
Slice, Majority/Minority Filter, Sieve Classes, Clump Classes), described in
[Image processing tools](image-processing.md#class-maps-classification).

| Classifier | Learns from | Needs |
| --- | --- | --- |
| **Train MLP on ROIs** | each ROI pixel's spectrum | always available |
| **Train CNN on ROIs** | the patch of pixels around each ROI pixel | PyTorch |
| **Train ViT on ROIs** | the patch of pixels around each ROI pixel | PyTorch |
| **Maximum Likelihood** | each class's mean and covariance | always available |
| **Mahalanobis Distance** | each class's mean, and the pooled covariance | always available |
| **K-Means Clustering** | the image itself (no ROIs) | always available |

The CNN and ViT need PyTorch: Varda offers to install it the first time you
pick one (see [Optional features](optional-features.md#cnn-and-vit-classifiers-and-learned-matchers-pytorch)).

## Training data: ROIs

The supervised classifiers train on the ROIs of the workspace the image is
open in. Each **ROI class** is one class: ROIs sharing a name are pooled.
Tick the classes to use in **ROI classes** (all of them by default; at least
two).

- **Which pixels.** A pixel belongs to an ROI when its center is inside it.
  Only valid pixels count: no-data pixels, and pixels missing half or more
  of their good bands, are left out.
- **Bands.** Every band is used. Bands marked bad (and the odd missing value)
  are filled by linear interpolation along each spectrum, not removed.
- **Class numbers.** Classes are numbered from 0 in the order their first
  ROI was drawn (among those ticked). The class color is the color of the
  class's first ROI.
- **Overlapping ROIs of different classes.** The MLP, CNN and ViT train on
  such a pixel once for each class, with conflicting labels. Maximum
  Likelihood and Mahalanobis Distance give it to the later class. Avoid
  overlaps.
- **Class sizes.** The MLP, CNN and ViT train on every ROI pixel, so a class
  with more pixels has more weight (a larger class acts like a larger prior).
  Maximum Likelihood and Mahalanobis Distance treat every class as equally
  likely, whatever its size.

## Outputs

Every supervised classifier makes the same result, named after the image
(for example "scene MLP classes"):

- **Class:** the number of the most probable class for each pixel (0, 1, 2,
  …, in the order above). Class names and colors come with the result, so
  Varda's views and the class map tools show them.
- **P(*class*):** one band per class, the classifier's probability (0 to 1)
  for that class. They sum to 1 at each pixel. What they mean depends on the
  classifier (see each section).
- **No data:** invalid pixels are no data (NaN) in every band.

Every valid pixel gets one of your classes. There is no "unclassified"
class and no rejection threshold, so a material you didn't train on goes to
whichever class fits least badly. To flag uncertain pixels, make a mask from
a **P(*class*)** band or from the highest of them (Band Math, Threshold to
Mask: see [Image math and masks](image-processing.md#image-math-and-masks)).

## Train MLP on ROIs

A multi-layer perceptron (a small neural network) trained on the spectra
inside the ROIs, in plain numpy. Each pixel is classified from its own
spectrum only.

| Setting | Meaning | Range | Default |
| --- | --- | --- | --- |
| **ROI classes** | The classes to train on | at least two | all |
| **Hidden Layers** | Number of hidden layers | 1–6 | 2 |
| **Neurons Per Layer** | Width of each hidden layer | 2–512 | 32 |
| **Epochs** | Passes through the training pixels | 1–5000 | 200 |
| **Learning Rate** | Adam step size | 0.00001–1 | 0.01 |
| **Seed** | Seeds the starting weights and the shuffling | 0–2147483647 | 0 |

How it works:

- Each band is standardized with the mean and standard deviation of the
  training pixels.
- Hidden units are tanh; the output is a softmax over the classes.
- Weights start from Glorot (Xavier) uniform values, biases from 0.
- Training minimizes cross-entropy with Adam (β₁ 0.9, β₂ 0.999, ε 10⁻⁸)
  on shuffled mini-batches of 256 pixels. There is no regularization, early
  stopping or validation split: it always runs every epoch.
- **Seed** seeds the starting weights and the shuffling. The same image,
  ROIs, settings and seed give the same result.

The result also records the seed, the layer sizes (bands, hidden layers,
classes) and the **final loss**: the mean cross-entropy (natural log) over the last
epoch. The progress dialog shows the loss after each epoch; Varda keeps the
final value with the result but doesn't display it, so note it as training
ends.

## Train CNN on ROIs

A small convolutional network trained on square patches of pixels around
each ROI pixel, with the bands as channels. Each pixel is classified from
its neighborhood.

| Setting | Meaning | Range | Default |
| --- | --- | --- | --- |
| **ROI classes** | The classes to train on | at least two | all |
| **Patch Size** | Width of the square neighborhood, in pixels (odd; an even value is raised by 1) | 1–15 | 5 |
| **Channels** | Filters in each convolutional layer | 4–256 | 32 |
| **Conv Layers** | Number of convolutional layers | 1–4 | 2 |
| **Epochs** | Passes through the training patches | 1–2000 | 50 |
| **Learning Rate** | Adam step size | 0.000001–0.1 | 0.001 |
| **Batch Size** | Patches per training step | 4–4096 | 64 |
| **Seed** | Seeds the starting weights and the shuffling | 0–2147483647 | 0 |

How it works:

- **Patches.** Each patch is centered on its pixel. At the image's edges the
  image is mirrored (reflect padding). Invalid pixels inside a patch are
  replaced by the image's mean spectrum. Bands are standardized with the
  mean and standard deviation of every pixel of the training patches.
- **Network.** Each layer is a 3 × 3 convolution, batch normalization and
  ReLU; then the layers are averaged over the patch (global average pooling)
  and a linear layer gives the class scores, turned into probabilities by a
  softmax.
- **Training.** Cross-entropy, Adam (PyTorch's defaults apart from the
  learning rate), shuffled mini-batches. No regularization, early stopping
  or validation split.
- **Where it runs.** On an NVIDIA GPU (CUDA) if there is one, else an Apple
  GPU (MPS), else the CPU.
- **Repeatability.** Before the network is built, **Seed** seeds PyTorch,
  numpy and Python's random numbers, so the starting weights and the
  shuffling are fixed, and Varda asks PyTorch for deterministic algorithms
  (cuDNN deterministic, benchmarking off). The same seed, settings and ROIs
  give the same result on the same device and PyTorch version. GPU
  arithmetic differs slightly from CPU arithmetic, and some GPU operations
  have no deterministic version, so results can differ a little between
  CPU, CUDA and MPS, or between PyTorch versions.

The result records the patch size, the seed, the final loss (as for the
MLP), the device (cpu, cuda or mps) and the PyTorch version; the
description says, e.g., "… (seed 0, PyTorch 2.5.1 on mps)".

## Train ViT on ROIs

A small vision transformer on the same patches as the CNN. Its tokens are
the patch's pixel spectra (one per pixel), unlike the original ViT, whose
tokens are blocks of pixels.

| Setting | Meaning | Range | Default |
| --- | --- | --- | --- |
| **ROI classes** | The classes to train on | at least two | all |
| **Patch Size** | As for the CNN | 1–15 | 5 |
| **Embedding Size** | Length of each token's vector | 8–512 | 64 |
| **Attention Heads** | Heads per attention layer; must divide the embedding size | 1–16 | 4 |
| **Transformer Layers** | Number of encoder layers | 1–8 | 2 |
| **Epochs**, **Learning Rate**, **Batch Size**, **Seed** | As for the CNN | | 50, 0.001, 64, 0 |

How it works: each pixel spectrum is projected linearly to the embedding
size; a learned class token and learned position embeddings are added; the
encoder layers are pre-norm, with a feed-forward width of twice the
embedding size and no dropout; the class token, normalized, goes through a
linear layer and a softmax. Patches, standardization, training, the
device and repeatability are as for the CNN, and the result records the
same things.

## Maximum Likelihood

Gaussian maximum-likelihood classification, through Spectral Python (SPy).
Each class is modeled by the mean and covariance of its training pixels,
and each pixel goes to the class under which it is most likely.

| Setting | Meaning | Range | Default |
| --- | --- | --- | --- |
| **ROI classes** | The classes to train on | at least two | all |
| **Components** | Principal components to classify on; 0 = automatic | 0–200 | 0 |

**Dimensions.** A class's covariance can only be inverted when it has more
pixels than dimensions, and a 400-band image needs hundreds of pixels per
class. So Varda may classify on principal components instead of bands. With
*b* bands and *n* pixels in the smallest class, the number of dimensions
*k* is:

- **Components** set (*c* > 0): *k* = the smallest of *c*, *b* and *n* − 1.
- **Components** 0: *k* = *b* (all bands) if *n* ≥ 2*b*; otherwise
  *k* = *n* ÷ 2 (rounded down), kept between 2 and the smaller of 30 and *b*.

When *k* < *b*, the principal components come from the covariance of every
valid pixel of the image (not just the training pixels); the classes are
then modeled on the first *k* components. Each class needs at least 3 valid
pixels and more than *k*; otherwise Varda names it and stops. The progress
dialog shows *k* ("training on *k* dimensions"); you can also work it out
from the rule above.

**Probabilities.** Each class's score is −½ ln|Σ| − ½ D², where Σ is the
class covariance and D² the pixel's squared Mahalanobis distance from the
class mean, with the covariance estimated with N − 1. The **P(*class*)**
bands are a softmax of these scores: the posterior probability if the
classes really were Gaussian and equally likely beforehand. Real classes
rarely are, and in many dimensions these probabilities are close to 0 or 1
for nearly every pixel, so read them as relative confidence.

## Mahalanobis Distance

Each pixel goes to the class whose mean is nearest, measured with one
covariance shared by all classes: the class covariances averaged, weighted
by their pixel counts. Settings, dimensions and outputs are as for Maximum
Likelihood. **P(*class*)** is a softmax of −½ D²: the posterior if the
classes were Gaussian with that shared covariance and equally likely.

## K-Means Clustering

Groups the image's valid pixels into clusters of similar spectra, with no
ROIs. A starting point for finding materials, not an identification.

| Setting | Meaning | Range | Default |
| --- | --- | --- | --- |
| **Clusters** | Number of clusters to look for | 2–50 | 8 |
| **Iterations** | Maximum number of iterations | 1–200 | 20 |

How it works (SPy's k-means): the starting centers are spaced evenly along
the diagonal from the image's per-band minimum to its per-band maximum, so
there is no randomness and every run gives the same result. Each iteration
assigns every pixel to its nearest center (Euclidean distance on the raw
values, all bands, not standardized) and moves each center to the mean of
its pixels. It stops when no pixel changes cluster, or after **Iterations**.
Bands with larger values or more variance count for more.

The result has one **Class** band (0, 1, 2, …; "Cluster 1" is 0), with no
probability bands. A cluster that ends up empty is dropped, so you can get
fewer clusters than you asked for. The cluster centers, the number of
iterations run, and whether it converged aren't kept.

## Reporting your results

What to state in a methods section, what the quality measures mean, and
what to cite. See also [Reporting results from Varda](reporting-results.md)
for what applies to every process.

### What to state

- The classifier and every setting. The result's record has them (see
  [What Varda records](reporting-results.md#what-varda-records-and-what-it-doesnt)).
- The training data: each class's name, its number of ROIs and of training
  pixels, and how you chose them. Varda records which ROI classes you
  ticked, but not the ROIs' shapes or pixel counts: save the session, or
  export the ROIs from the ROI Manager (**Export...**), to keep them.
- Any band subset, spatial subset or preprocessing of the input.
- For Maximum Likelihood and Mahalanobis Distance: the number of dimensions
  *k*, and whether they were bands or principal components.
- For the MLP, CNN and ViT: the seed and the final training loss, and for
  the CNN and ViT the device (CPU, CUDA or MPS) and PyTorch version (both
  in the result's description).
- For K-Means: the number of clusters found, and how you named them.
- Any clean-up with the class map tools (filter size, minimum group size).

Settings the dialogs don't show:

| Classifier | Setting |
| --- | --- |
| MLP | tanh hidden units, softmax output, cross-entropy; Adam (β₁ 0.9, β₂ 0.999, ε 10⁻⁸); mini-batches of 256; Glorot uniform starting weights; bands standardized on the training pixels |
| CNN | 3 × 3 convolutions with padding, batch normalization and ReLU; global average pooling; linear output; cross-entropy; Adam |
| ViT | Linear embedding of each pixel spectrum; learned class token and position embeddings; pre-norm encoder layers, feed-forward width 2 × embedding size, no dropout; cross-entropy; Adam |
| CNN and ViT | Reflect padding at the edges; invalid pixels in a patch replaced by the image mean spectrum; bands standardized on all pixels of the training patches; PyTorch's default layer initialization; deterministic algorithms requested (warnings, not errors, where none exists) |
| Maximum Likelihood, Mahalanobis | Equal priors; covariances with N − 1; principal components from the covariance of all valid image pixels; at least 3 pixels per class |
| K-Means | Euclidean distance on unstandardized values; starting centers evenly spaced from the per-band minimum to maximum; stops when no pixel changes cluster |

### Uncertainty and quality

- **Varda doesn't measure accuracy.** No classifier sets aside validation
  data or reports accuracy or a confusion matrix. The final loss says how
  well the network fits its *training* pixels, which says little about how
  well it classifies the rest of the image: a network with enough epochs can
  fit its training pixels almost perfectly. To measure accuracy, use
  independent test data (below).
- **Probabilities aren't calibrated.** For the MLP, CNN and ViT they are
  softmax outputs, which neural networks tend to make overconfident. For
  Maximum Likelihood and Mahalanobis Distance they hold only as far as the
  Gaussian, equal-prior model holds. Use them to rank pixels or to mask out
  doubtful ones, and don't report them as the chance a pixel is correct
  unless you have checked them against test data.
- **Reproducibility.** Maximum Likelihood, Mahalanobis Distance and
  K-Means are deterministic: the same image, ROIs and settings give the
  same map. The MLP, CNN and ViT are random but seeded: the same seed
  reproduces the map (for the CNN and ViT, on the same device and PyTorch
  version). A seed fixes one outcome of training; it doesn't make that
  outcome typical. Train with several seeds (three or more) and report how
  much the map or the accuracy changes.
- **Unseen materials.** Every pixel is given one of your classes (see
  [Outputs](#outputs)), so check areas that none of your ROIs represent.
- **K-Means** has no quality measure. Its clusters depend on the starting
  centers and on the scale of each band; they are groups of similar spectra,
  not materials, until you identify them.

**Measuring accuracy.**

1. Draw test ROIs as classes of their own (for example "Basalt test"), away
   from the training ROIs. Pixels next to each other are alike, and a CNN or
   ViT patch reaches into its neighbors, so test ROIs that touch training
   ROIs make the accuracy look better than it is.
2. Train with only the training classes ticked in **ROI classes**.
3. For each test class, make a mask with **ROI to Mask** (Processing → Image
   Math), ticking that one class.
4. Export the result and the masks (**File → Export Image…**, GeoTIFF) and,
   for each test class, count its pixels by **Class** value. Each test class
   gives one row of the confusion matrix. In Python:

   ```python
   import numpy as np, rasterio

   classMap = rasterio.open("scene_MLP_classes.tif").read(1)  # the Class band
   mask = rasterio.open("basalt_test_mask.tif").read(1) == 1
   values = classMap[mask & np.isfinite(classMap)].astype(int)
   print(np.bincount(values, minlength=4))  # 4 = number of classes
   ```

   (Or export the test ROIs from the ROI Manager and use your GIS's zonal
   statistics.)
5. Report the confusion matrix, the overall accuracy, each class's
   producer's and user's accuracy, and the number of test ROIs and pixels
   per class (Congalton 1991). Kappa (Cohen 1960) is often asked for; report
   it alongside these, not instead. Pixels in one ROI aren't independent, so
   a confidence interval computed from the pixel count is too narrow. If you
   report areas of classes, correct them for the errors in the confusion
   matrix (Olofsson et al. 2014).

### References

- Accuracy assessment: Congalton, R. G. (1991). A review of assessing the
  accuracy of classifications of remotely sensed data. *Remote Sensing of
  Environment*, 37(1), 35–46.
- Kappa: Cohen, J. (1960). A coefficient of agreement for nominal scales.
  *Educational and Psychological Measurement*, 20(1), 37–46.
- Area estimation and accuracy: Olofsson, P., Foody, G. M., Herold, M.,
  Stehman, S. V., Woodcock, C. E., & Wulder, M. A. (2014). Good practices for
  estimating area and assessing accuracy of land change. *Remote Sensing of
  Environment*, 148, 42–57.
- Maximum likelihood and Mahalanobis distance classification: Richards,
  J. A., & Jia, X. (2006). *Remote Sensing Digital Image Analysis: An
  Introduction* (4th ed.). Springer.
- K-means (the iteration Varda uses): Lloyd, S. P. (1982). Least squares
  quantization in PCM. *IEEE Transactions on Information Theory*, 28(2),
  129–137.
- Adam: Kingma, D. P., & Ba, J. (2015). Adam: a method for stochastic
  optimization. *Proc. International Conference on Learning Representations
  (ICLR)*.
- Starting weights (MLP): Glorot, X., & Bengio, Y. (2010). Understanding the
  difficulty of training deep feedforward neural networks. *Proc. AISTATS*,
  PMLR 9, 249–256.
- Batch normalization (CNN): Ioffe, S., & Szegedy, C. (2015). Batch
  normalization: accelerating deep network training by reducing internal
  covariate shift. *Proc. ICML*, PMLR 37, 448–456.
- Transformers: Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones,
  L., Gomez, A. N., Kaiser, Ł., & Polosukhin, I. (2017). Attention is all you
  need. *Advances in Neural Information Processing Systems*, 30, 5998–6008.
- Vision transformer: Dosovitskiy, A., Beyer, L., Kolesnikov, A.,
  Weissenborn, D., Zhai, X., Unterthiner, T., Dehghani, M., Minderer, M.,
  Heigold, G., Gelly, S., Uszkoreit, J., & Houlsby, N. (2021). An image is
  worth 16x16 words: transformers for image recognition at scale. *Proc.
  ICLR*.
- Calibration of neural networks: Guo, C., Pleiss, G., Sun, Y., &
  Weinberger, K. Q. (2017). On calibration of modern neural networks. *Proc.
  ICML*, PMLR 70, 1321–1330.
- PyTorch: Paszke, A., et al. (2019). PyTorch: an imperative style,
  high-performance deep learning library. *Advances in Neural Information
  Processing Systems*, 32, 8024–8035.
- Spectral Python (SPy), used for Maximum Likelihood, Mahalanobis Distance
  and K-Means: cite it as its documentation asks, with its version (Varda
  uses 0.24 or 0.25).
