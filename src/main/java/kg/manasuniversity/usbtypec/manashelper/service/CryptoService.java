package kg.manasuniversity.usbtypec.manashelper.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.BadPaddingException;
import javax.crypto.Cipher;
import javax.crypto.IllegalBlockSizeException;
import javax.crypto.NoSuchPaddingException;
import javax.crypto.spec.SecretKeySpec;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.util.Base64;

@Service
public class CryptoService {
  private static final String ALGORITHM = "AES";
  private final SecretKeySpec secretKeySpec;

  public CryptoService(@Value("${crypto.secret-key}") String secretKey) {
    secretKeySpec = new SecretKeySpec(secretKey.getBytes(), ALGORITHM);
  }

  public String encrypt(String plainText) throws IllegalStateException {
    try {
      Cipher cipher = Cipher.getInstance(ALGORITHM);
      cipher.init(Cipher.ENCRYPT_MODE, secretKeySpec);

      byte[] encrypted = cipher.doFinal(plainText.getBytes());
      return Base64.getEncoder().encodeToString(encrypted);
    } catch (NoSuchPaddingException | IllegalBlockSizeException | BadPaddingException | InvalidKeyException |
             NoSuchAlgorithmException e) {
      throw new IllegalStateException("Encryption failed", e);
    }
  }

  public String decrypt(String encryptedText) throws IllegalStateException {
    try {
      Cipher cipher = Cipher.getInstance(ALGORITHM);
      cipher.init(Cipher.DECRYPT_MODE, secretKeySpec);

      byte[] decoded = Base64.getDecoder().decode(encryptedText);
      return new String(cipher.doFinal(decoded));

    } catch (Exception e) {
      throw new IllegalStateException("Decryption failed", e);
    }
  }
}
