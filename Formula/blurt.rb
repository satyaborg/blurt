class Blurt < Formula
  include Language::Python::Virtualenv

  desc "Local speech-to-text for macOS using MLX Whisper on Apple Silicon"
  homepage "https://github.com/satyaborg/blurt"
  url "https://files.pythonhosted.org/packages/source/b/blurt/blurt-0.1.0.tar.gz"
  sha256 "d874fa1ec0f360315527e792dc7762949a6eb9fbe5ff0385eaa9f5d04f58527e"
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
