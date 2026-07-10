param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Files
)

$ErrorActionPreference = "Stop"

function Get-MarkdownFilesFromDialog {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = "Select Markdown files to normalize"
    $dialog.Filter = "Markdown files (*.md)|*.md|All files (*.*)|*.*"
    $dialog.Multiselect = $true

    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        return @($dialog.FileNames)
    }

    return @()
}

function Get-InlineCodeRanges {
    param([string]$Line)

    $ranges = New-Object System.Collections.Generic.List[object]
    $matches = [regex]::Matches($Line, '`+')
    $index = 0

    while ($index + 1 -lt $matches.Count) {
        $ranges.Add([pscustomobject]@{
            Start = $matches[$index].Index
            End = $matches[$index + 1].Index + $matches[$index + 1].Length
        })
        $index += 2
    }

    return $ranges
}

function Get-LinkDestinationRanges {
    param([string]$Line)

    $ranges = New-Object System.Collections.Generic.List[object]
    $matches = [regex]::Matches($Line, '!?\[[^\]]*\]\(')

    foreach ($match in $matches) {
        $start = $match.Index + $match.Length
        $depth = 1
        $escaped = $false
        $index = $start

        while ($index -lt $Line.Length) {
            $char = $Line[$index]

            if ($escaped) {
                $escaped = $false
            } elseif ($char -eq '\') {
                $escaped = $true
            } elseif ($char -eq '(') {
                $depth += 1
            } elseif ($char -eq ')') {
                $depth -= 1
                if ($depth -eq 0) {
                    $ranges.Add([pscustomobject]@{
                        Start = $start
                        End = $index
                    })
                    break
                }
            }

            $index += 1
        }
    }

    return $ranges
}

function Test-ProtectedIndex {
    param(
        [int]$Index,
        [object[]]$Ranges
    )

    foreach ($range in $Ranges) {
        if ($Index -ge $range.Start -and $Index -lt $range.End) {
            return $true
        }
    }

    return $false
}

function Get-QuotePositions {
    param([string]$Text)

    $positions = New-Object System.Collections.Generic.List[int]
    $lineMatches = [regex]::Matches($Text, "[^\r\n]*(?:\r\n|\n|\r|$)")
    $offset = 0
    $inFence = $false

    foreach ($lineMatch in $lineMatches) {
        $line = $lineMatch.Value
        if ($line.Length -eq 0) {
            continue
        }

        if ($line -match '^\s*(```+|~~~+)') {
            $inFence = -not $inFence
            $offset += $line.Length
            continue
        }

        if (-not $inFence) {
            $ranges = @()
            $ranges += @(Get-InlineCodeRanges -Line $line)
            $ranges += @(Get-LinkDestinationRanges -Line $line)

            for ($index = 0; $index -lt $line.Length; $index += 1) {
                if ($line[$index] -eq '"' -and -not (Test-ProtectedIndex -Index $index -Ranges $ranges)) {
                    $positions.Add($offset + $index)
                }
            }
        }

        $offset += $line.Length
    }

    return $positions
}

function Convert-DoubleQuotes {
    param([string]$Text)

    $positions = Get-QuotePositions -Text $Text
    $replaceCount = $positions.Count
    $warning = $false

    if ($positions.Count % 2 -eq 1) {
        $replaceCount = $positions.Count - 1
        $warning = $true
    }

    if ($replaceCount -le 0) {
        return [pscustomobject]@{
            Text = $Text
            Converted = 0
            OddQuoteWarning = $warning
        }
    }

    $chars = $Text.ToCharArray()
    $openQuote = [char]0x201C
    $closeQuote = [char]0x201D

    for ($index = 0; $index -lt $replaceCount; $index += 1) {
        $chars[$positions[$index]] = if ($index % 2 -eq 0) { $openQuote } else { $closeQuote }
    }

    return [pscustomobject]@{
        Text = -join $chars
        Converted = $replaceCount
        OddQuoteWarning = $warning
    }
}

function Read-Utf8Text {
    param([string]$Path)

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $hasBom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF

    if ($hasBom) {
        $text = [System.Text.Encoding]::UTF8.GetString($bytes, 3, $bytes.Length - 3)
    } else {
        $text = [System.Text.Encoding]::UTF8.GetString($bytes)
    }

    return [pscustomobject]@{
        Text = $text
        HasBom = $hasBom
    }
}

function Write-Utf8Text {
    param(
        [string]$Path,
        [string]$Text,
        [bool]$HasBom
    )

    $encoding = New-Object System.Text.UTF8Encoding($HasBom)
    [System.IO.File]::WriteAllText($Path, $Text, $encoding)
}

function Invoke-NormalizeFile {
    param([string]$Path)

    $resolved = (Resolve-Path -LiteralPath $Path).Path

    if ([System.IO.Path]::GetExtension($resolved).ToLowerInvariant() -ne ".md") {
        throw "Only Markdown files are supported: $resolved"
    }

    $input = Read-Utf8Text -Path $resolved
    $output = Convert-DoubleQuotes -Text $input.Text

    if ($output.Text -ne $input.Text) {
        Write-Utf8Text -Path $resolved -Text $output.Text -HasBom $input.HasBom
    }

    $remainingDoubleQuotes = ([regex]::Matches($output.Text, '"')).Count
    $singleQuotes = ([regex]::Matches($output.Text, "'")).Count
    $otherPunctuation = ([regex]::Matches($output.Text, '[,;:!?]')).Count

    Write-Host "Processed: $resolved"
    Write-Host "Halfwidth double quotes converted: $($output.Converted); remaining: $remainingDoubleQuotes"
    Write-Host "Halfwidth single quotes: $singleQuotes (count only)"
    Write-Host "Other halfwidth punctuation: $otherPunctuation (count only)"

    if ($output.Text -ne $input.Text) {
        Write-Host "Status: modified in place"
    } else {
        Write-Host "Status: no changes needed"
    }

    if ($output.OddQuoteWarning) {
        Write-Host "Notice: odd number of halfwidth double quotes found. The last one was kept unchanged."
    }
}

if (-not $Files -or $Files.Count -eq 0) {
    $Files = Get-MarkdownFilesFromDialog
}

if (-not $Files -or $Files.Count -eq 0) {
    Write-Host "No files selected."
    exit 0
}

$hadError = $false
for ($index = 0; $index -lt $Files.Count; $index += 1) {
    if ($index -gt 0) {
        Write-Host ""
    }

    try {
        Invoke-NormalizeFile -Path $Files[$index]
    } catch {
        $hadError = $true
        Write-Host "Failed: $($Files[$index])"
        Write-Host "Reason: $($_.Exception.Message)"
    }
}

if ($hadError) {
    exit 1
}

exit 0
