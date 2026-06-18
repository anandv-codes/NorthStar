# Lambda Deployment Package Builder
# Creates a zip file ready to upload to AWS Lambda

$BackendDir = Get-Location
$LambdaDeployDir = Join-Path $BackendDir "lambda_deployment"
$ZipFile = Join-Path $BackendDir "northstar-note-processor.zip"

Write-Host "=== Building Lambda Deployment Package ===" -ForegroundColor Green

# Clean up old deployment folder if it exists
if (Test-Path $LambdaDeployDir) {
    Write-Host "Removing old deployment directory..."
    Remove-Item $LambdaDeployDir -Recurse -Force
}

# Create fresh deployment directory
Write-Host "Creating deployment directory..."
mkdir $LambdaDeployDir | Out-Null
# Install dependencies to deployment folder
Write-Host "Installing Python dependencies..."
if (Test-Path "requirements_lambda.txt") {
    # Lambda runs Amazon Linux x86_64. We are building on Windows, so we must
    # fetch Linux wheels explicitly (otherwise pydantic_core etc. ship the wrong
    # native binary -> "No module named 'pydantic_core._pydantic_core'").
    # --python-version MUST match the Lambda runtime.
    pip install -r requirements_lambda.txt -t $LambdaDeployDir `
        --platform manylinux2014_x86_64 `
        --implementation cp `
        --python-version 3.12 `
        --only-binary=:all: --upgrade --quiet
    Write-Host "[OK] Dependencies installed (linux x86_64 wheels)"
}
else {
    Write-Host "WARNING: requirements.txt not found"
}

# Copy app code
Write-Host "Copying app code..."
Copy-Item .\app $LambdaDeployDir\app -Recurse -Force
Write-Host "[OK] App code copied"

# Create Lambda handler wrapper
Write-Host "Creating Lambda handler..."
$HandlerContent = @'
import sys
sys.path.insert(0, '/var/task')

from app.lambdas.note_processor import lambda_handler

# Lambda expects this handler function
__all__ = ['lambda_handler']
'@

Add-Content -Path (Join-Path $LambdaDeployDir "lambda_function.py") -Value $HandlerContent
Write-Host "[OK] Handler created"

# Remove old zip if it exists
if (Test-Path $ZipFile) {
    Remove-Item $ZipFile -Force
}

# Create zip file.
# NOTE: Do NOT use Compress-Archive here. On Windows PowerShell 5.1 it writes zip
# entries with backslash separators (pydantic_core\_pydantic_core...so), which
# Linux/Lambda cannot read as nested paths -> "No module named
# 'pydantic_core._pydantic_core'". Windows' bundled bsdtar writes forward slashes.
Write-Host "Creating zip package..."
tar -a -c -f $ZipFile -C $LambdaDeployDir .
Write-Host "[OK] Zip created: $ZipFile"

# Show file size
$Size = (Get-Item $ZipFile).Length / 1MB
Write-Host "Package size: $([Math]::Round($Size, 2)) MB" -ForegroundColor Yellow

Write-Host "`n=== Next Steps ===" -ForegroundColor Green
Write-Host "1. Go to AWS Lambda Console"
Write-Host "2. Create function: NorthStar-Note-Processor"
Write-Host "3. Upload this zip: $ZipFile"
Write-Host "4. Set Handler: lambda_function.lambda_handler"
Write-Host "5. Set environment variables (SUPABASE_URL, SUPABASE_KEY, etc.)"
Write-Host "6. Add SQS trigger"

Write-Host "`nDone!" -ForegroundColor Green
