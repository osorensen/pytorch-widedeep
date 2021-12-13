"""
During the development of the package I realised that there is a typing
inconsistency. The input components of a Wide and Deep model are of type
nn.Module. These change type internally to nn.Sequential. While nn.Sequential
is an instance of nn.Module the oppossite is, of course, not true. This does
not affect any funcionality of the package, but it is something that needs
fixing. However, while fixing is simple (simply define new attributes that
are the nn.Sequential objects), its implications are quite wide within the
package (involves changing a number of tests and tutorials). Therefore, I
will introduce that fix when I do a major release. For now, we live with it.
"""

import warnings

import torch
import torch.nn as nn

from pytorch_widedeep.wdtypes import *  # noqa: F403
from pytorch_widedeep.models.tab_mlp import MLP, get_activation_fn
from pytorch_widedeep.models.tabnet.tab_net import TabNetPredLayer
from pytorch_widedeep.models import fds_layer

warnings.filterwarnings("default", category=UserWarning)

use_cuda = torch.cuda.is_available()
device = torch.device("cuda" if use_cuda else "cpu")


class WideDeep(nn.Module):
    r"""Main collector class that combines all ``wide``, ``deeptabular``
    (which can be a number of architectures), ``deeptext`` and
    ``deepimage`` models.

    There are two options to combine these models that correspond to the
    two main architectures that ``pytorch-widedeep`` can build.

        - Directly connecting the output of the model components to an ouput neuron(s).

        - Adding a `Fully-Connected Head` (FC-Head) on top of the deep models.
          This FC-Head will combine the output form the ``deeptabular``, ``deeptext`` and
          ``deepimage`` and will be then connected to the output neuron(s).

    Parameters
    ----------
    wide: ``nn.Module``, Optional, default = None
        ``Wide`` model. I recommend using the ``Wide`` class in this
        package. However, it is possible to use a custom model as long as
        is consistent with the required architecture, see
        :class:`pytorch_widedeep.models.wide.Wide`
    deeptabular: ``nn.Module``, Optional, default = None
        currently ``pytorch-widedeep`` implements a number of possible
        architectures for the ``deeptabular`` component. See the documenation
        of the package. I recommend using the ``deeptabular`` components in
        this package. However, it is possible to use a custom model as long
        as is  consistent with the required architecture.
    deeptext: ``nn.Module``, Optional, default = None
        Model for the text input. Must be an object of class ``DeepText``
        or a custom model as long as is consistent with the required
        architecture. See
        :class:`pytorch_widedeep.models.deep_text.DeepText`
    deepimage: ``nn.Module``, Optional, default = None
        Model for the images input. Must be an object of class
        ``DeepImage`` or a custom model as long as is consistent with the
        required architecture. See
        :class:`pytorch_widedeep.models.deep_image.DeepImage`
    deephead: ``nn.Module``, Optional, default = None
        Custom model by the user that will receive the outtput of the deep
        component. Typically a FC-Head (MLP)
    head_hidden_dims: List, Optional, default = None
        Alternatively, the ``head_hidden_dims`` param can be used to
        specify the sizes of the stacked dense layers in the fc-head e.g:
        ``[128, 64]``. Use ``deephead`` or ``head_hidden_dims``, but not
        both.
    head_dropout: float, default = 0.1
        If ``head_hidden_dims`` is not None, dropout between the layers in
        ``head_hidden_dims``
    head_activation: str, default = "relu"
        If ``head_hidden_dims`` is not None, activation function of the head
        layers. One of ``tanh``, ``relu``, ``gelu`` or ``leaky_relu``
    head_batchnorm: bool, default = False
        If ``head_hidden_dims`` is not None, specifies if batch
        normalizatin should be included in the head layers
    head_batchnorm_last: bool, default = False
        If ``head_hidden_dims`` is not None, boolean indicating whether or
        not to apply batch normalization to the last of the dense layers
    head_linear_first: bool, default = False
        If ``head_hidden_dims`` is not None, boolean indicating whether
        the order of the operations in the dense layer. If ``True``:
        ``[LIN -> ACT -> BN -> DP]``. If ``False``: ``[BN -> DP -> LIN ->
        ACT]``
    enforce_positive: bool, default = False
        If final layer has activation function or not. Important if you are using
        loss functions non-negative input restrictions, e.g. RMSLE, or if you know
        your predictions are limited only to <0, inf)
    enforce_positive_activation: str, default = "softplus"
        Activation function to enforce positive output from final layer. Use
        "softplus" or "relu".
    fds: bool, default = False
        If the feature distribution smoothing layer should be applied before the
        final prediction layer. Only available for objective='regressor'.
    fds_config: dict, default = None
        dictionary defining specific values for FeatureDistributionSmoothing layer
    pred_dim: int, default = 1
        Size of the final wide and deep output layer containing the
        predictions. `1` for regression and binary classification or number
        of classes for multiclass classification.

    Examples
    --------

    >>> from pytorch_widedeep.models import TabResnet, DeepImage, DeepText, Wide, WideDeep
    >>> embed_input = [(u, i, j) for u, i, j in zip(["a", "b", "c"][:4], [4] * 3, [8] * 3)]
    >>> column_idx = {k: v for v, k in enumerate(["a", "b", "c"])}
    >>> wide = Wide(10, 1)
    >>> deeptabular = TabResnet(blocks_dims=[8, 4], column_idx=column_idx, embed_input=embed_input)
    >>> deeptext = DeepText(vocab_size=10, embed_dim=4, padding_idx=0)
    >>> deepimage = DeepImage(pretrained=False)
    >>> model = WideDeep(wide=wide, deeptabular=deeptabular, deeptext=deeptext, deepimage=deepimage)


    .. note:: While I recommend using the ``wide`` and ``deeptabular`` components
        within this package when building the corresponding model components,
        it is very likely that the user will want to use custom text and image
        models. That is perfectly possible. Simply, build them and pass them
        as the corresponding parameters. Note that the custom models MUST
        return a last layer of activations (i.e. not the final prediction) so
        that  these activations are collected by ``WideDeep`` and combined
        accordingly. In addition, the models MUST also contain an attribute
        ``output_dim`` with the size of these last layers of activations. See
        for example :class:`pytorch_widedeep.models.tab_mlp.TabMlp`

    """

    def __init__(
        self,
        wide: Optional[nn.Module] = None,
        deeptabular: Optional[nn.Module] = None,
        deeptext: Optional[nn.Module] = None,
        deepimage: Optional[nn.Module] = None,
        deephead: Optional[nn.Module] = None,
        head_hidden_dims: Optional[List[int]] = None,
        head_activation: str = "relu",
        head_dropout: float = 0.1,
        head_batchnorm: bool = False,
        head_batchnorm_last: bool = False,
        head_linear_first: bool = False,
        enforce_positive: bool = False,
        enforce_positive_activation: str = "softplus",
        pred_dim: int = 1,
        fds: bool = False,
        fds_config: Optional[dict] = None,
    ):
        super(WideDeep, self).__init__()

        self._check_model_components(
            wide,
            deeptabular,
            deeptext,
            deepimage,
            deephead,
            head_hidden_dims,
            pred_dim,
        )

        # required as attribute just in case we pass a deephead
        self.pred_dim = pred_dim

        # The main 5 components of the wide and deep assemble
        self.wide = wide
        self.deeptabular = deeptabular
        self.deeptext = deeptext
        self.deepimage = deepimage
        self.deephead = deephead
        self.enforce_positive = enforce_positive
        self.fds = fds

        if self.deeptabular is not None:
            self.is_tabnet = deeptabular.__class__.__name__ == "TabNet"
        else:
            self.is_tabnet = False

        if self.deephead is None and head_hidden_dims is not None:
            self._build_deephead(
                head_hidden_dims,
                head_activation,
                head_dropout,
                head_batchnorm,
                head_batchnorm_last,
                head_linear_first,
            )
        elif self.deephead is not None:
            pass
        elif self.fds:
            if (
                not self.deeptabular
                or self.pred_dim != 1
                #or self.wide.pred_dim != self.deeptabular.output_dim
            ):
                raise ValueError(
                    """Feature Distribution Smoothing is supported only with deeptabular
                    component without deephead with single output neuron. If used, wide
                    component must have pred_dim == deeptabular.output_dim """
                )

            if fds_config:
                self.FDS = fds_layer.FDS(**fds_config)
            else:
                self.FDS = fds_layer.FDS(feature_dim=self.deeptabular.output_dim)
            self.FDS_dropout = nn.Dropout(p=self.deeptabular.mlp_dropout)
            self.pred_layer = nn.Linear(self.deeptabular.output_dim, self.pred_dim)
        else:
            self._add_pred_layer()

        if self.enforce_positive:
            self.enf_pos = get_activation_fn(enforce_positive_activation)

    def forward(self, X: Dict[str, Tensor], y: Optional[Tensor]=None, epoch: Optional[int]=None):
        y_pred = self._forward_wide(X)
        if self.deephead:
            y_pred = self._forward_deephead(X, y_pred)
        elif self.training and self.fds:
            y_pred, deep_features = self._forward_deep(X, y_pred, y, epoch)
            if self.enforce_positive:
                return self.enf_pos(y_pred), deep_features
            else:
                return y_pred, deep_features
        else:
            y_pred = self._forward_deep(X, y_pred)

        if self.enforce_positive:
            return self.enf_pos(y_pred)
        else:
            return y_pred

    def _build_deephead(
        self,
        head_hidden_dims,
        head_activation,
        head_dropout,
        head_batchnorm,
        head_batchnorm_last,
        head_linear_first,
    ):
        deep_dim = 0
        if self.deeptabular is not None:
            deep_dim += self.deeptabular.output_dim
        if self.deeptext is not None:
            deep_dim += self.deeptext.output_dim
        if self.deepimage is not None:
            deep_dim += self.deepimage.output_dim

        head_hidden_dims = [deep_dim] + head_hidden_dims
        self.deephead = MLP(
            head_hidden_dims,
            head_activation,
            head_dropout,
            head_batchnorm,
            head_batchnorm_last,
            head_linear_first,
        )

        self.deephead.add_module(
            "head_out", nn.Linear(head_hidden_dims[-1], self.pred_dim)
        )

    def _add_pred_layer(self):
        if self.deeptabular is not None:
            if self.is_tabnet:
                self.deeptabular = nn.Sequential(
                    self.deeptabular,
                    TabNetPredLayer(self.deeptabular.output_dim, self.pred_dim),
                )
            else:
                self.deeptabular = nn.Sequential(
                    self.deeptabular,
                    nn.Linear(self.deeptabular.output_dim, self.pred_dim),
                )
        if self.deeptext is not None:
            self.deeptext = nn.Sequential(
                self.deeptext, nn.Linear(self.deeptext.output_dim, self.pred_dim)
            )
        if self.deepimage is not None:
            self.deepimage = nn.Sequential(
                self.deepimage, nn.Linear(self.deepimage.output_dim, self.pred_dim)
            )

    def _forward_wide(self, X):
        if self.wide is not None:
            out = self.wide(X["wide"])
        else:
            batch_size = X[list(X.keys())[0]].size(0)
            out = torch.zeros(batch_size, self.pred_dim).to(device)

        return out

    def _forward_deephead(self, X, wide_out):
        if self.deeptabular is not None:
            if self.is_tabnet:
                tab_out = self.deeptabular(X["deeptabular"])
                deepside, M_loss = tab_out[0], tab_out[1]
            else:
                deepside = self.deeptabular(X["deeptabular"])
        else:
            deepside = torch.FloatTensor().to(device)
        if self.deeptext is not None:
            deepside = torch.cat([deepside, self.deeptext(X["deeptext"])], axis=1)
        if self.deepimage is not None:
            deepside = torch.cat([deepside, self.deepimage(X["deepimage"])], axis=1)

        deephead_out = self.deephead(deepside)
        deepside_out = nn.Linear(deephead_out.size(1), self.pred_dim).to(device)

        if self.is_tabnet:
            res = (wide_out.add_(deepside_out(deephead_out)), M_loss)
        else:
            res = wide_out.add_(deepside_out(deephead_out))

        return res

    def _forward_deep(self, X, wide_out, y=None, epoch=None):
        if self.deeptabular is not None:
            if self.is_tabnet:
                tab_out, M_loss = self.deeptabular(X["deeptabular"])
                wide_out.add_(tab_out)
            else:
                deeptab_features = self.deeptabular(X["deeptabular"])
                deeptab_s = deeptab_features
                if self.training and self.fds:
                    deeptab_s = self.FDS.smooth(deeptab_s, y, epoch)
                    deeptab_s = self.FDS_dropout(deeptab_s)
                if self.fds:
                    wide_out.add_(self.pred_layer(deeptab_s))
                else:
                    wide_out.add_(deeptab_features)
                if self.training and self.fds:
                    return wide_out, deeptab_features
        if self.deeptext is not None:
            wide_out.add_(self.deeptext(X["deeptext"]))
        if self.deepimage is not None:
            wide_out.add_(self.deepimage(X["deepimage"]))
        if self.is_tabnet:
            res = (wide_out, M_loss)
        else:
            res = wide_out

        return res

    @staticmethod  # noqa: C901
    def _check_model_components(  # noqa: C901
        wide,
        deeptabular,
        deeptext,
        deepimage,
        deephead,
        head_hidden_dims,
        pred_dim,
    ):

        if wide is not None:
            assert wide.wide_linear.weight.size(1) == pred_dim, (
                "the 'pred_dim' of the wide component ({}) must be equal to the 'pred_dim' "
                "of the deep component and the overall model itself ({})".format(
                    wide.wide_linear.weight.size(1), pred_dim
                )
            )
        if deeptabular is not None and not hasattr(deeptabular, "output_dim"):
            raise AttributeError(
                "deeptabular model must have an 'output_dim' attribute. "
                "See pytorch-widedeep.models.deep_text.DeepText"
            )
        if deeptabular is not None:
            is_tabnet = deeptabular.__class__.__name__ == "TabNet"
            has_wide_text_or_image = (
                wide is not None or deeptext is not None or deepimage is not None
            )
            if is_tabnet and has_wide_text_or_image:
                warnings.warn(
                    "'WideDeep' is a model comprised by multiple components and the 'deeptabular'"
                    " component is 'TabNet'. We recommend using 'TabNet' in isolation."
                    " The reasons are: i)'TabNet' uses sparse regularization which partially losses"
                    " its purpose when used in combination with other components."
                    " If you still want to use a multiple component model with 'TabNet',"
                    " consider setting 'lambda_sparse' to 0 during training. ii) The feature"
                    " importances will be computed only for TabNet but the model will comprise multiple"
                    " components. Therefore, such importances will partially lose their 'meaning'.",
                    UserWarning,
                )
        if deeptext is not None and not hasattr(deeptext, "output_dim"):
            raise AttributeError(
                "deeptext model must have an 'output_dim' attribute. "
                "See pytorch-widedeep.models.deep_text.DeepText"
            )
        if deepimage is not None and not hasattr(deepimage, "output_dim"):
            raise AttributeError(
                "deepimage model must have an 'output_dim' attribute. "
                "See pytorch-widedeep.models.deep_text.DeepText"
            )
        if deephead is not None and head_hidden_dims is not None:
            raise ValueError(
                "both 'deephead' and 'head_hidden_dims' are not None. Use one of the other, but not both"
            )
        if (
            head_hidden_dims is not None
            and not deeptabular
            and not deeptext
            and not deepimage
        ):
            raise ValueError(
                "if 'head_hidden_dims' is not None, at least one deep component must be used"
            )
        if deephead is not None:
            deephead_inp_feat = next(deephead.parameters()).size(1)
            output_dim = 0
            if deeptabular is not None:
                output_dim += deeptabular.output_dim
            if deeptext is not None:
                output_dim += deeptext.output_dim
            if deepimage is not None:
                output_dim += deepimage.output_dim
            assert deephead_inp_feat == output_dim, (
                "if a custom 'deephead' is used its input features ({}) must be equal to "
                "the output features of the deep component ({})".format(
                    deephead_inp_feat, output_dim
                )
            )
