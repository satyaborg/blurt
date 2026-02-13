class Blurt < Formula
  include Language::Python::Virtualenv

  desc "Local speech-to-text for macOS using MLX Whisper on Apple Silicon"
  homepage "https://github.com/satyaborg/blurt"
  url "https://files.pythonhosted.org/packages/source/b/blurt/blurt-0.1.1.tar.gz"
  sha256 "9ca0fec664323b3552c65ba4f98167ff9382be01b1d5149ce66184dad46c8cbf"
  license "MIT"

  depends_on "python@3.12"
  depends_on "portaudio"
  depends_on :macos

  # After publishing to PyPI, generate resource stanzas:
  #   pip install homebrew-pypi-poet
  #   poet blurt
  # Paste output here.

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "blurt #{version}", shell_output("#{bin}/blurt --version")
  end
end
