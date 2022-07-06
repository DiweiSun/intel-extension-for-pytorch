import torch
import torch.nn as nn
import unittest
import copy
from torch.testing._internal.common_utils import TestCase
import intel_extension_for_pytorch as ipex

ipex_emb_fn = ipex.nn.functional._embeddingbag._embeddingbag
aten_emb_fn = ipex.nn.functional._embeddingbag.torch_embedding_bag

class TestEMB(TestCase):

    def _test_emb(self, mode):
        aten_emb = nn.EmbeddingBag(10, 5, mode="sum", sparse=True)
        aten_emb = aten_emb.bfloat16().float()
        ipex_emb = copy.deepcopy(aten_emb)
        bf16_emb = copy.deepcopy(aten_emb).bfloat16()
        # a batch of 2 samples of 4 indices each
        input = torch.LongTensor([1,2,4,5,4,3,2,9])
        offsets = torch.LongTensor([0, 4])
        # aten path
        torch.embedding_bag = aten_emb_fn
        aten_out = aten_emb(input, offsets)
        aten_out.sum().backward()

        # ipex fast path (both fp32/bf16)
        torch.embedding_bag = ipex_emb_fn
        ipex_out = ipex_emb(input, offsets)
        ipex_out.sum().backward()

        self.assertEqual(aten_out, ipex_out)
        self.assertEqual(aten_emb.weight.grad.data._nnz(), ipex_emb.weight.grad.data._nnz())
        self.assertEqual(aten_emb.weight.grad.data.sparse_dim(), ipex_emb.weight.grad.data.sparse_dim())
        self.assertEqual(aten_emb.weight.grad.data.dense_dim(), ipex_emb.weight.grad.data.dense_dim())
        self.assertEqual(aten_emb.weight.grad.data.is_coalesced(), ipex_emb.weight.grad.data.is_coalesced())
        self.assertEqual(aten_emb.weight.grad.data._indices(), ipex_emb.weight.grad.data._indices())
        self.assertEqual(aten_emb.weight.grad.data._values(), ipex_emb.weight.grad.data._values())

        if mode == 'sum':
            bf16_out = bf16_emb(input, offsets)
            bf16_out.sum().backward()
            self.assertEqual(aten_out.bfloat16(), bf16_out)
            self.assertEqual(bf16_emb.weight.grad.data._values().dtype, torch.bfloat16)
            self.assertEqual(aten_emb.weight.grad.data._nnz(), ipex_emb.weight.grad.data._nnz())
            self.assertEqual(aten_emb.weight.grad.data.sparse_dim(), ipex_emb.weight.grad.data.sparse_dim())
            self.assertEqual(aten_emb.weight.grad.data.dense_dim(), ipex_emb.weight.grad.data.dense_dim())
            self.assertEqual(aten_emb.weight.grad.data.is_coalesced(), ipex_emb.weight.grad.data.is_coalesced())
            self.assertEqual(aten_emb.weight.grad.data._indices(), ipex_emb.weight.grad.data._indices())
            self.assertEqual(aten_emb.weight.grad.data._values().bfloat16().float(), ipex_emb.weight.grad.data._values().float())

    def test_emb_fallback_path(self):
        self._test_emb(mode='mean')

    def test_emb_fast_path(self):
        self._test_emb(mode='sum')

    def test_emb_jit_scriptable(self):
        emb = nn.EmbeddingBag(10, 3, mode='sum', sparse=True)
        input = torch.LongTensor([1,2,4,5,4,3,2,9])
        offsets = torch.LongTensor([0,1,2,3,4,5,6,7])
        ref_out = emb(input, offsets)
        script_emb = torch.jit.script(emb)
        out = script_emb(input, offsets)
        self.assertEqual(out, ref_out)

if __name__ == '__main__':
    test = unittest.main()
