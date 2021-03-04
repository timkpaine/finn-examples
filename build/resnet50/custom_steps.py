# Copyright (c) 2020, Xilinx
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of FINN nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# from finn.core.modelwrapper import ModelWrapper
import numpy as np
import copy

from finn.transformation.fold_constants import FoldConstants

from finn.transformation.infer_datatypes import InferDataTypes
from finn.transformation.general import (
    ConvertSubToAdd,
    ConvertDivToMul,
    GiveReadableTensorNames,
    GiveUniqueNodeNames,
    SortGraph,
    RemoveUnusedTensors,
    GiveUniqueParameterTensors,
    RemoveStaticGraphInputs,
    ApplyConfig,
)

from finn.transformation.streamline.absorb import (
    AbsorbScalarMulAddIntoTopK,
    AbsorbAddIntoMultiThreshold,
    AbsorbMulIntoMultiThreshold,
    FactorOutMulSignMagnitude,
    Absorb1BitMulIntoMatMul,
    Absorb1BitMulIntoConv,
)

from finn.transformation.streamline.collapse_repeated import (
    CollapseRepeatedAdd,
    CollapseRepeatedMul,
)

from finn.transformation.streamline.reorder import (
    MoveAddPastMul,
    MoveScalarMulPastMatMul,
    MoveScalarAddPastMatMul,
    MoveAddPastConv,
    MoveScalarMulPastConv,
    MoveScalarLinearPastInvariants,
    MoveMaxPoolPastMultiThreshold
)

from finn.transformation.streamline.round_thresholds import RoundAndClipThresholds
from finn.transformation.streamline.sign_to_thres import ConvertSignToThres
from finn.transformation.batchnorm_to_affine import BatchNormToAffine

## just for not linear
from finn.transformation.streamline.reorder import (
    MoveLinearPastEltwiseAdd,
    MoveLinearPastFork,
    )

from finn.transformation.double_to_single_float import DoubleToSingleFloat   
from finn.transformation.streamline.remove import RemoveIdentityOps
from finn.core.datatype import DataType

from finn.transformation.infer_shapes import InferShapes
from finn.transformation.infer_datatypes import InferDataTypes
from finn.transformation.infer_data_layouts import InferDataLayouts
from finn.transformation.general import (
    GiveReadableTensorNames,
    GiveUniqueNodeNames,
    SortGraph,
    RemoveUnusedTensors
)


from finn.transformation.streamline.absorb import (
    AbsorbConsecutiveTransposes,
    AbsorbTransposeIntoMultiThreshold,
)

from finn.transformation.streamline.collapse_repeated import (
    CollapseRepeatedAdd,
    CollapseRepeatedMul,
)

from finn.transformation.streamline.reorder import (
    MoveScalarLinearPastInvariants,
    MoveAddPastMul,
    MoveScalarMulPastMatMul,
    MoveScalarAddPastMatMul,
)

from finn.transformation.insert_topk import InsertTopK
from finn.transformation.streamline.round_thresholds import RoundAndClipThresholds
from finn.transformation.double_to_single_float import DoubleToSingleFloat
import finn.transformation.fpgadataflow.convert_to_hls_layers as to_hls
from finn.transformation.lower_convs_to_matmul import LowerConvsToMatMul

from finn.core.modelwrapper import ModelWrapper
from finn.custom_op.registry import getCustomOp
from finn.builder.build_dataflow_config import DataflowBuildConfig

from finn.transformation.fpgadataflow.prepare_ip import PrepareIP
from finn.transformation.fpgadataflow.hlssynth_ip import HLSSynthIP
from finn.transformation.fpgadataflow.replace_verilog_relpaths import (
    ReplaceVerilogRelPaths)

from finn.transformation.move_reshape import RemoveCNVtoFCFlatten
    
from finn.util.config import extract_model_config_to_json
from finn.transformation.fpgadataflow.set_fifo_depths import (
    InsertAndSetFIFODepths,
    RemoveShallowFIFOs,
)
from finn.transformation.fpgadataflow.insert_dwc import InsertDWC
from finn.transformation.fpgadataflow.insert_fifo import InsertFIFO

def step_resnet50_tidy(model: ModelWrapper, cfg: DataflowBuildConfig):
    model = model.transform(GiveUniqueParameterTensors())
    model = model.transform(InferShapes())
    model = model.transform(FoldConstants())
    model = model.transform(RemoveStaticGraphInputs())
    model = model.transform(GiveUniqueNodeNames())
    model = model.transform(GiveReadableTensorNames())
    model = model.transform(InferDataTypes())
    model = model.transform(InsertTopK())
    model = model.transform(InferShapes())
    model = model.transform(GiveUniqueNodeNames())
    model = model.transform(GiveReadableTensorNames())
    model = model.transform(InferDataTypes())
    return model

def step_resnet50_streamline_linear(model: ModelWrapper, cfg: DataflowBuildConfig):
    streamline_transformations = [
        AbsorbScalarMulAddIntoTopK(), # before MoveAddPastMul to avoid int->float 
        ConvertSubToAdd(),
        ConvertDivToMul(),
        RemoveIdentityOps(),
        CollapseRepeatedMul(),
        BatchNormToAffine(),
        ConvertSignToThres(),
        MoveAddPastMul(),
        MoveScalarAddPastMatMul(),
        MoveAddPastConv(),
        MoveScalarMulPastMatMul(),
        MoveScalarMulPastConv(),
        MoveScalarLinearPastInvariants(),
        MoveAddPastMul(),
        CollapseRepeatedAdd(),
        CollapseRepeatedMul(),
        AbsorbAddIntoMultiThreshold(),
        FactorOutMulSignMagnitude(),
        MoveMaxPoolPastMultiThreshold(),
        AbsorbMulIntoMultiThreshold(),
        Absorb1BitMulIntoMatMul(),
        Absorb1BitMulIntoConv(),
    ]
    for trn in streamline_transformations:
        model = model.transform(trn)
        model = model.transform(GiveUniqueNodeNames())
    return model

def step_resnet50_streamline_nonlinear(model: ModelWrapper, cfg: DataflowBuildConfig):
    streamline_transformations = [
        MoveLinearPastEltwiseAdd(),
        MoveLinearPastFork(),
    ]
    for trn in streamline_transformations:
        model = model.transform(trn)
        model = model.transform(GiveUniqueNodeNames())
    return model


def step_resnet50_streamline(model: ModelWrapper, cfg: DataflowBuildConfig):

    for iter_id in range(4):
        model = step_resnet50_streamline_linear(model, cfg)
        model = step_resnet50_streamline_nonlinear(model, cfg)

        # big loop tidy up
        model = model.transform(RemoveUnusedTensors())
        model = model.transform(GiveReadableTensorNames())
        model = model.transform(InferDataTypes())
        model = model.transform(SortGraph())

    model = model.transform(DoubleToSingleFloat())

    return model


def step_resnet50_convert_to_hls(model: ModelWrapper, cfg: DataflowBuildConfig):
    model.set_tensor_datatype(model.graph.input[0].name, DataType.UINT8)
    model = model.transform(InferDataLayouts())
    
    try:
        from finn.transformation.fpgadataflow.infer_doublepacked_dsp import InferDoublePackedConv
        model = model.transform(InferDoublePackedConv([1]))
    except:
        print(" FINN Experimental not available. Using non-packed convolution ")


    model = model.transform(DoubleToSingleFloat())
    model = model.transform(InferDataTypes())
    model = model.transform(SortGraph())

    to_hls_transformations = [
        to_hls.InferAddStreamsLayer,
        LowerConvsToMatMul,
        to_hls.InferChannelwiseLinearLayer,
        to_hls.InferPool_Batch,
        AbsorbTransposeIntoMultiThreshold,
        RoundAndClipThresholds,
        to_hls.InferQuantizedStreamingFCLayer,
        to_hls.InferThresholdingLayer,
        AbsorbConsecutiveTransposes,
        to_hls.InferConvInpGen,
        to_hls.InferDuplicateStreamsLayer,
        to_hls.InferLabelSelectLayer,

    ]
    for trn in to_hls_transformations:
        model = model.transform(trn())
        model = model.transform(InferDataLayouts())
        model = model.transform(GiveUniqueNodeNames())
        model = model.transform(InferDataTypes())

    model = model.transform(RemoveCNVtoFCFlatten())
    model = model.transform(GiveReadableTensorNames())
    model = model.transform(RemoveUnusedTensors())
    model = model.transform(SortGraph())

    return model



def step_resnet50_set_fifo_depths(model: ModelWrapper, cfg: DataflowBuildConfig):
    """
    Depending on the auto_fifo_depths setting, do one of the following:
    * if auto_fifo_depths=True:  Run the `InsertAndSetFIFODepths` transformation
    to attempt to determine the FIFO sizes that provide full throughput. Involves
    running stitched-IP rtlsim and may take a long time.
    * if auto_fifo_depths=False:  Assume the folding config file contains FIFO
    sizes as well. Runs the `InsertFIFO` transformation, then
    `ApplyConfig(cfg.folding_config_file)`, and finally `RemoveShallowFIFOs`.
    Coherency with config file node naming is ensured by calling
    `GiveUniqueNodeNames`.
    """

    if cfg.auto_fifo_depths:
        model = model.transform(
            InsertAndSetFIFODepths(
                cfg._resolve_fpga_part(),
                cfg._resolve_hls_clk_period(),
                vivado_ram_style=cfg.large_fifo_mem_style.value,
            )
        )
    else:
        # assume folding cfg json contains FIFO sizes too
        # insert DWCs, FIFOs and run ApplyConfig once more
        model = model.transform(InsertDWC())
        # need to make sure all FIFOs are created so that their depth can be
        # set by ApplyConfig, so create_shallow_fifos=True
        model = model.transform(InsertFIFO(create_shallow_fifos=True))
        model = model.transform(GiveUniqueNodeNames())
        model = model.transform(GiveReadableTensorNames())
        if cfg.folding_config_file is not None:
            model = model.transform(ApplyConfig(cfg.folding_config_file))
        # remove any shallow FIFOs
        model = model.transform(RemoveShallowFIFOs())

    # extract the final configuration and save it as json
    hw_attrs = [
        "PE",
        "SIMD",
        "ram_style",
        "depth",
        "impl_style",
        "resType",
        "mem_mode",
        "runtime_writeable_weights",
    ]
    extract_model_config_to_json(
        model, cfg.output_dir + "/final_hw_config.json", hw_attrs
    )

    return model
