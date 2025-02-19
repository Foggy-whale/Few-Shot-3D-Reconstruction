import torch
import torch.nn as nn
import torch.nn.functional as func
import numpy as np

class FeatureVoxel(nn.Module):
    def __init__(self,resolution,coord_range,channels):
        super(FeatureVoxel,self).__init__()
        self.voxel = torch.Tensor(resolution[0] + 1,resolution[1] + 1,resolution[2] + 1,channels)
        self.voxel = nn.parameter.Parameter(self.voxel)
        self.grid_matrix = [(0,0,0),(0,0,1),(0,1,0),(0,1,1),(1,0,0),(1,0,1),(1,1,0),(1,1,1)]
        self.grid_martix = torch.tensor(np.array(self.grid_matrix))
        self.grid_martix = self.grid_martix.unsqueeze(1)
        self.channels = channels
        self.resolution = resolution
        self.coord_range = coord_range

    @torch.no_grad()
    def convert_to_voxel_coordinate(self,positions):
        coord_range = self.coord_range
        coord_range = coord_range.to(self.voxel.device)
        resolution = self.resolution
        resolution = resolution.to(self.voxel.device)
        positions = positions - coord_range[0].unsqueeze(0)
        positions = positions / ((coord_range[1] - coord_range[0]).unsqueeze(0))
        mask = (positions<1) & (positions>=0)
        mask = mask[:,0] & mask[:,1] & mask[:,2]
        positions = positions * resolution
        return positions, mask

    def forward(self,positions):
        with torch.no_grad():
            origin_batch_size = positions.shape[0]
            channels = self.channels
            positions,mask = self.convert_to_voxel_coordinate(positions)
            positions = positions[mask]
            batch_size = positions.shape[0]
            indices_on_grid = positions.to(torch.long)
            positions_in_grid = positions - indices_on_grid
            positions_x,positions_y,positions_z = torch.unbind(positions_in_grid,1)
            positions_x = torch.stack([1-positions_x,positions_x]).permute(1,0).unsqueeze(1).unsqueeze(1).repeat(1,channels,1,1)
            positions_y = torch.stack([1-positions_y,positions_y]).permute(1,0).unsqueeze(1).unsqueeze(1).repeat(1,channels,1,1)
            positions_z = torch.stack([1-positions_z,positions_z]).permute(1,0).unsqueeze(1).unsqueeze(1).repeat(1,channels,1,1)

            indices_on_grid = indices_on_grid.unsqueeze(0).repeat(8,1,1)
            indices_on_grid = indices_on_grid + self.grid_martix.to(self.voxel.device).to(torch.long)

        features = self.voxel[indices_on_grid[:,:,0],indices_on_grid[:,:,1],indices_on_grid[:,:,2]].permute(1,2,0)#n*c*8
        features = features.reshape(batch_size,channels,2,4)
        features = torch.matmul(positions_x,features)
        features = features.reshape(batch_size,channels,2,2)
        features = torch.matmul(positions_y,features)
        features = features.reshape(batch_size,channels,2,1)
        features = torch.matmul(positions_z,features)
        features = features.squeeze(-1).squeeze(-1)
        final_features = torch.zeros((origin_batch_size,channels)).to(self.voxel.device).to(self.voxel.dtype)
        final_features[mask] = features
        return final_features