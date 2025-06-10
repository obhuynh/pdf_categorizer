import torch

print(f"PyTorch Version: {torch.__version__}")

# Check if the MPS backend is available (this is the key for Apple Silicon)
if torch.backends.mps.is_available():
    print("✅ MPS (Apple Silicon GPU) backend is available!")
    
    # Set the device to MPS
    device = torch.device("mps")
    
    # Create a test tensor on the CPU
    cpu_tensor = torch.rand(3, 3)
    print(f"\nTensor on CPU:\n{cpu_tensor}")
    
    # Move the tensor to the MPS device (the GPU)
    gpu_tensor = cpu_tensor.to(device)
    print(f"\nTensor on GPU (MPS Device):\n{gpu_tensor}")
    
    print("\n🚀 Successfully moved tensor to GPU. Your setup is correct!")

elif not torch.backends.mps.is_built():
    print("❌ MPS not available because the installed PyTorch binary was not built with MPS support.")
    print("Please reinstall PyTorch. Make sure you are using Python 3.8 or later on an M-series Mac.")

else:
    print("❌ MPS not available. You are likely running on a non-Apple Silicon Mac or an unsupported configuration.")
    print("Falling back to CPU.")
    device = torch.device("cpu")